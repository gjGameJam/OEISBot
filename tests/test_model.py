"""The local-model client: both API shapes, and what counts as unavailable. No server is contacted."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from oeisbot.model import LocalModel, ModelUnavailable

URL = "http://model.test"


class Response:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def stub_server(monkeypatch, by_path: dict, sent: list | None = None):
    """Answer each path with a payload, or raise it if it is an exception."""
    def urlopen(req, timeout=None):
        path = getattr(req, "full_url", req)[len(URL):]
        if sent is not None and getattr(req, "data", None):
            sent.append((path, json.loads(req.data)))
        answer = by_path[path]
        if isinstance(answer, Exception):
            raise answer
        return Response(answer)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


def test_ollama_chat_sends_the_context_size(monkeypatch):
    sent: list = []
    stub_server(monkeypatch, {"/api/chat": {"message": {"content": "hello"}}}, sent)
    model = LocalModel(name="qwen2.5-coder:14b", url=URL, api="ollama", context=8192)
    assert model.chat([{"role": "user", "content": "hi"}], temperature=0.5, max_tokens=64) == "hello"
    path, payload = sent[0]
    assert path == "/api/chat" and payload["stream"] is False and payload["model"] == "qwen2.5-coder:14b"
    assert payload["options"] == {"temperature": 0.5, "num_ctx": 8192, "num_predict": 64}


def test_openai_chat_uses_the_completions_shape(monkeypatch):
    sent: list = []
    stub_server(monkeypatch, {"/v1/chat/completions": {"choices": [{"message": {"content": "hi there"}}]}}, sent)
    assert LocalModel(name="local", url=URL, api="openai").chat([{"role": "user", "content": "hi"}]) == "hi there"
    path, payload = sent[0]
    assert path == "/v1/chat/completions" and payload["max_tokens"] == 2048 and "options" not in payload


def test_chat_without_a_server_raises_model_unavailable(monkeypatch):
    stub_server(monkeypatch, {"/api/chat": urllib.error.URLError("connection refused")})
    with pytest.raises(ModelUnavailable, match="connection refused"):
        LocalModel(url=URL, api="ollama").chat([])


@pytest.mark.parametrize("api, path, listing, name, problem", [
    ("ollama", "/api/tags", {"models": [{"name": "qwen2.5-coder:14b"}]}, "qwen2.5-coder:14b", None),
    ("ollama", "/api/tags", {"models": [{"name": "qwen2.5-coder:14b"}]}, "qwen2.5-coder", None),   # tag ignored
    ("ollama", "/api/tags", {"models": [{"name": "other:7b"}]}, "qwen2.5-coder:14b", "not found"),
    ("ollama", "/api/tags", {"models": []}, "qwen2.5-coder:14b", "have: none"),
    ("openai", "/v1/models", {"data": [{"id": "local-coder"}]}, "local-coder", None),
    ("openai", "/v1/models", {"data": [{"id": "other"}]}, "local-coder", "not found"),
])
def test_available_checks_the_listing(monkeypatch, api, path, listing, name, problem):
    stub_server(monkeypatch, {path: listing})
    said = LocalModel(name=name, url=URL, api=api).available()
    assert said is None if problem is None else problem in said


def test_available_reports_a_server_that_does_not_answer(monkeypatch):
    stub_server(monkeypatch, {"/api/tags": urllib.error.URLError("refused")})
    assert "no model server at" in LocalModel(url=URL, api="ollama").available()
