from ccgram.session_protocol.messages import parse_records, read_entries


def test_qwen_messages_and_tools_are_normalized(tmp_path) -> None:
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        "\n".join(
            [
                '{"uuid":"u1","type":"user","timestamp":"2026-01-01T00:00:00Z","message":{"role":"user","parts":[{"text":"Fix it"}]}}',
                '{"uuid":"a1","type":"assistant","timestamp":"2026-01-01T00:00:01Z","message":{"role":"model","parts":[{"text":"I will inspect it"},{"thought":true,"text":"reasoning"},{"functionCall":{"id":"call-1","name":"read_file","args":{"path":"x.py"}}}]}}',
                '{"uuid":"t1","type":"tool_result","timestamp":"2026-01-01T00:00:02Z","message":{"role":"user","parts":[{"functionResponse":{"id":"call-1","response":"contents"}}]}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    entries = read_entries(transcript, provider="qwen")
    records, _ = parse_records(entries, "qwen")
    assert [record.role for _, record in records] == ["user", "agent", "agent"]
    assert records[1][1].parts[0]["text"] == "I will inspect it"
    assert records[1][1].parts[1]["type"] == "thinking"
    assert records[1][1].parts[2]["type"] == "tool"
    assert records[2][1].results[0] == ("call-1", "contents", False)
