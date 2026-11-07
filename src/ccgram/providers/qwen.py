"""Qwen Code provider.

Qwen stores project-scoped sessions as JSONL under
``~/.qwen/projects/<sanitized-cwd>/chats/<session-id>.jsonl``.  The provider is
deliberately hookless for now: transcript discovery is the source of truth and
the Herdr integration can be added later without changing the resume contract.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ccgram.providers._jsonl import JsonlProvider
from ccgram.providers.base import (
    ProviderCapabilities,
    ResumableSession,
    SessionStartEvent,
)

_STALE_TRANSCRIPT_MAX_AGE_SECS = 120.0
_DISCOVERY_SCAN_LIMIT = 50


def _qwen_projects_dir() -> Path:
    return Path(os.environ.get("QWEN_HOME", Path.home() / ".qwen")) / "projects"


def encode_qwen_cwd(cwd: str) -> str:
    """Encode a workspace path using Qwen's project directory convention."""
    return cwd.replace("\\", "-").replace("/", "-")


def _session_files(cwd: str) -> list[tuple[float, Path]]:
    directory = _qwen_projects_dir() / encode_qwen_cwd(cwd) / "chats"
    if not directory.is_dir():
        return []
    result: list[tuple[float, Path]] = []
    try:
        for path in directory.glob("*.jsonl"):
            try:
                result.append((path.stat().st_mtime, path))
            except OSError:
                continue
    except OSError:
        return []
    result.sort(key=lambda pair: pair[0], reverse=True)
    return result


def _read_session_header(path: Path) -> dict[str, Any] | None:
    try:
        with path.open(encoding="utf-8") as stream:
            first = json.loads(stream.readline())
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(first, dict):
        return None
    return first


def _header_cwd(header: dict[str, Any]) -> str:
    cwd = header.get("cwd")
    return cwd if isinstance(cwd, str) else ""


def _header_session_id(header: dict[str, Any], path: Path) -> str:
    session_id = header.get("sessionId")
    if isinstance(session_id, str) and session_id:
        return session_id
    return path.stem


def _summary(path: Path) -> str:
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                data = json.loads(line)
                message = data.get("message") if isinstance(data, dict) else None
                parts = message.get("parts") if isinstance(message, dict) else None
                if data.get("type") == "user" and isinstance(parts, list):
                    text = next(
                        (part.get("text") for part in parts if isinstance(part, dict) and part.get("text")),
                        "",
                    )
                    if isinstance(text, str) and text.strip():
                        return text.strip().replace("\n", " ")[:120]
    except (OSError, ValueError, UnicodeDecodeError):
        pass
    return path.stem


class QwenProvider(JsonlProvider):
    """AgentProvider implementation for Qwen Code."""

    _CAPS = ProviderCapabilities(
        name="qwen",
        launch_command="qwen",
        supports_resume=True,
        supports_continue=True,
        supports_structured_transcript=True,
        supports_incremental_read=True,
        supports_status_snapshot=False,
        has_yolo_confirmation=True,
    )

    def make_launch_args(
        self,
        resume_id: str | None = None,
        use_continue: bool = False,
    ) -> str:
        if resume_id:
            from ccgram.providers.base import RESUME_ID_RE

            if not RESUME_ID_RE.match(resume_id):
                raise ValueError(f"Invalid resume_id: {resume_id!r}")
            return f"--resume {resume_id}"
        return "--continue" if use_continue else ""

    def discover_resumable_sessions(
        self,
        *,
        cwd: str | None = None,
        limit: int | None = None,
    ) -> list[ResumableSession]:
        if not cwd:
            return []
        result: list[ResumableSession] = []
        for mtime, path in _session_files(cwd)[: _DISCOVERY_SCAN_LIMIT]:
            header = _read_session_header(path)
            if not header:
                continue
            header_cwd = _header_cwd(header)
            if not header_cwd or os.path.abspath(header_cwd) != os.path.abspath(cwd):
                continue
            result.append(
                ResumableSession(
                    session_id=_header_session_id(header, path),
                    summary=_summary(path),
                    cwd=header_cwd,
                    provider_name="qwen",
                    mtime=mtime,
                )
            )
            if limit is not None and len(result) >= limit:
                break
        return result

    def discover_transcript(
        self,
        cwd: str,
        window_key: str,
        *,
        max_age: float | None = None,
    ) -> SessionStartEvent | None:
        if not cwd:
            return None
        age_limit = (
            _STALE_TRANSCRIPT_MAX_AGE_SECS if max_age is None else float(max_age)
        )
        now = time.time()
        resolved_cwd = os.path.abspath(cwd)
        for mtime, path in _session_files(cwd)[:_DISCOVERY_SCAN_LIMIT]:
            if age_limit > 0 and now - mtime > age_limit:
                break
            header = _read_session_header(path)
            if not header or os.path.abspath(_header_cwd(header)) != resolved_cwd:
                continue
            return SessionStartEvent(
                session_id=_header_session_id(header, path),
                cwd=_header_cwd(header),
                transcript_path=str(path),
                window_key=window_key,
            )
        return None
