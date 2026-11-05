"""call_llm on the Anthropic SDK: parses the JSON text reply, sends the agreed request shape, and turns every
failure (rate limit, non-JSON, refusal, missing key) into {"error": ...}. The client is faked; no network.
"""
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.engine import config
from app.engine.agents import base_agent


class FakeMessages:
    def __init__(self, result):
        self.result, self.calls = result, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _reply(*texts, stop_reason="end_turn"):
    blocks = [SimpleNamespace(type="thinking", thinking="")] + [SimpleNamespace(type="text", text=t) for t in texts]
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


@pytest.fixture()
def fake_client(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")

    def install(result) -> FakeMessages:
        messages = FakeMessages(result)
        monkeypatch.setattr(base_agent, "_client", SimpleNamespace(beta=SimpleNamespace(messages=messages)))
        return messages

    return install


def test_parses_json_text_and_sends_agreed_request(fake_client):
    messages = fake_client(_reply('{"why_flagged": "Profit grew 612% ', 'YoY.", "what_changed": "x"}'))
    assert base_agent.call_llm("SYS", "USER") == {"why_flagged": "Profit grew 612% YoY.", "what_changed": "x"}
    [kw] = messages.calls
    assert kw["model"] == "claude-opus-5-5" and kw["max_tokens"] == 2048
    assert kw["system"] == "SYS" and kw["messages"] == [{"role": "user", "content": "USER"}]
    assert kw["output_config"] == {"effort": "low"}
    assert kw["betas"] == ["server-side-fallback-2026-07-01"] and kw["fallbacks"] == "default"
    assert not {"temperature", "thinking", "budget_tokens"} & set(kw)


def test_rate_limit_returns_error(fake_client):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.RateLimitError("rate limited", response=httpx2.Response(429, request=request), body=None)
    fake_client(err)
    result = base_agent.call_llm("SYS", "USER")
    assert set(result) == {"error"} and "rate limited" in result["error"]


def test_non_json_refusal_and_missing_key(fake_client, monkeypatch):
    fake_client(_reply("Sure! Here is the note."))
    assert base_agent.call_llm("SYS", "USER") == {"error": "non-JSON narration"}
    fake_client(_reply('```json\n{"why_flagged": "a", "what_changed": "b"}\n```'))
    assert base_agent.call_llm("SYS", "USER") == {"why_flagged": "a", "what_changed": "b"}
    fake_client(_reply("", stop_reason="refusal"))
    assert base_agent.call_llm("SYS", "USER") == {"error": "refusal"}
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    assert base_agent.call_llm("SYS", "USER") == {"error": "ANTHROPIC_API_KEY not set"}
