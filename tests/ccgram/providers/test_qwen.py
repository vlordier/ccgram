import json
import os
import time
from pathlib import Path

import pytest

from ccgram.providers.qwen import QwenProvider, encode_qwen_cwd


def _write_session(root: Path, cwd: str, session_id: str = "11111111-1111-4111-8111-111111111111") -> Path:
    chats = root / "projects" / encode_qwen_cwd(cwd) / "chats"
    chats.mkdir(parents=True)
    path = chats / f"{session_id}.jsonl"
    path.write_text(
        json.dumps(
            {
                "uuid": "u1",
                "sessionId": session_id,
                "type": "user",
                "cwd": cwd,
                "message": {"role": "user", "parts": [{"text": "Fix the bug"}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_encode_qwen_cwd() -> None:
    assert encode_qwen_cwd("/Users/vincent/Work/counter-sim") == "-Users-vincent-Work-counter-sim"


def test_launch_args() -> None:
    provider = QwenProvider()
    assert provider.make_launch_args() == ""
    assert provider.make_launch_args(use_continue=True) == "--continue"
    assert provider.make_launch_args("11111111-1111-4111-8111-111111111111") == (
        "--resume 11111111-1111-4111-8111-111111111111"
    )
    with pytest.raises(ValueError):
        provider.make_launch_args("bad id")


def test_discover_and_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = "/Users/vincent/Work/counter-sim"
    path = _write_session(tmp_path, cwd)
    monkeypatch.setenv("QWEN_HOME", str(tmp_path))
    provider = QwenProvider()

    sessions = provider.discover_resumable_sessions(cwd=cwd)
    assert len(sessions) == 1
    assert sessions[0].provider_name == "qwen"
    assert sessions[0].summary == "Fix the bug"

    event = provider.discover_transcript(cwd, "herdr:@1", max_age=60)
    assert event is not None
    assert event.session_id == path.stem
    assert event.transcript_path == str(path)


def test_discover_ignores_stale_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = "/tmp/project"
    path = _write_session(tmp_path, cwd)
    old = time.time() - 3600
    os.utime(path, (old, old))
    monkeypatch.setenv("QWEN_HOME", str(tmp_path))
    assert QwenProvider().discover_transcript(cwd, "@1") is None
