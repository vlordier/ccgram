# Qwen provider integration research

Date: 2026-11-07

## Findings

The upstream project is `alexei-led/ccgram`. Its provider architecture is intentionally extensible: providers implement `AgentProvider`, expose `ProviderCapabilities`, and are registered from `src/ccgram/providers/__init__.py`.

Qwen Code 0.26.7 stores interactive sessions as JSONL files under:

```text
~/.qwen/projects/<encoded-cwd>/chats/<session-id>.jsonl
```

The records contain `type`, `sessionId`, `timestamp`, `cwd`, and a nested `message` object. Session IDs are UUIDs and Qwen resumes with:

```text
qwen --resume <session-id>
```

Qwen's own documentation also exposes a native Telegram channel, but that starts and owns Qwen sessions itself. It does not bind existing Herdr panes into CCGram.

## Required CCGram changes

1. Add `src/ccgram/providers/qwen.py`.
2. Register `QwenProvider` in `src/ccgram/providers/__init__.py`.
3. Add Qwen detection to `process_detection.py` and provider path detection in `__init__.py`.
4. Extend `session_protocol/messages.py` with a Qwen record adapter. The current normalizers understand Claude, Codex, Gemini, and Pi-like records but not Qwen's `message.parts` format.
5. Add Qwen fixtures and provider tests for discovery, resume arguments, JSONL parsing, and stale-session filtering.
6. Decide explicitly whether `supports_hook` is enabled. The Herdr integration can provide session metadata, but CCGram should not claim hook support until the event contract is stable.

## Recommended first implementation

Start as a hookless, transcript-backed provider:

- launch command: `qwen`
- resume: `--resume <uuid>`
- session discovery: newest chat file whose first user record has a matching `cwd`
- transcript path marker: `/.qwen/projects/` plus `/chats/`
- capabilities: structured transcript, resume, continue if verified, no CCGram-managed hook initially

This gives CCGram a safe read-only integration and avoids coupling the first version to Herdr internals. A second phase can consume Herdr events for immediate session binding and pane lifecycle updates.

## Primary sources

- [CCGram provider documentation](https://github.com/alexei-led/ccgram/blob/main/docs/providers.md)
- [CCGram provider protocol](https://github.com/alexei-led/ccgram/blob/main/src/ccgram/providers/base.py)
- [Qwen Code Telegram channel documentation](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/channels/telegram.md)
- [Qwen Code architecture](https://github.com/QwenLM/qwen-code/blob/main/docs/developers/architecture.md)
