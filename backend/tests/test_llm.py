import pytest
from pydantic import BaseModel

from app import llm
from app.llm import LLMError, LLMRateLimited, complete_json, extract_json


class Out(BaseModel):
    queries: list[str]


def test_extract_json_handles_fences_think_blocks_and_chatter():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('<think>hmm {"x": 0}</think>\nSure! {"a": 2} Hope that helps') == {"a": 2}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_complete_json_retries_with_error_feedback(monkeypatch):
    seen = []
    replies = iter(["this is not json", '{"queries": ["a", "b"]}'])

    def fake_chat(messages, model, temperature, max_tokens):
        seen.append(list(messages))
        return next(replies)

    monkeypatch.setattr(llm, "_chat", fake_chat)
    out = complete_json("sys", "user", Out)
    assert out.queries == ["a", "b"]
    assert len(seen) == 2
    assert "not valid" in seen[1][-1]["content"]          # the error was fed back
    assert "JSON schema" in seen[0][0]["content"]          # the schema was sent


def test_complete_json_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: '{"wrong": true}')
    with pytest.raises(LLMError):
        complete_json("sys", "user", Out, retries=1)


class FakeResp:
    def __init__(self, status, body=None, headers=None, text=""):
        self.status_code, self._body, self.headers, self.text = status, body, headers or {}, text

    def json(self):
        return self._body


def test_chat_retries_429_then_raises_rate_limited(monkeypatch):
    calls = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: calls.append(s))
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: FakeResp(429, headers={"retry-after": "1"}))
    with pytest.raises(LLMRateLimited):
        llm._chat([{"role": "user", "content": "x"}], None, 0.1, 10)
    assert len(calls) == 3  # three waits, four attempts


def test_chat_returns_content(monkeypatch):
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: FakeResp(200, {"choices": [{"message": {"content": "hello"}}]}))
    assert llm._chat([], None, 0.1, 10) == "hello"


def test_chat_surfaces_provider_errors(monkeypatch):
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: FakeResp(401, text="bad key"))
    with pytest.raises(LLMError, match="401"):
        llm._chat([], None, 0.1, 10)
