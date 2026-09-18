"""Client for the local code model. Runs in the harness process, never inside the sandbox
(the sandbox has no network, loopback included, so generated code cannot reach the model)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from . import config


class ModelClient(Protocol):
    name: str

    def chat(self, messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 2048) -> str: ...


class ModelUnavailable(Exception):
    pass


def _post(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise ModelUnavailable(f"{url}: {e}") from e


@dataclass
class LocalModel:
    name: str = config.MODEL_NAME
    url: str = config.MODEL_URL
    api: str = config.MODEL_API
    context: int = config.MODEL_CONTEXT
    timeout_s: float = 600.0

    def chat(self, messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 2048) -> str:
        if self.api == "ollama":
            # native API: lets us raise num_ctx (Ollama's default context silently truncates long prompts)
            out = _post(f"{self.url}/api/chat", {
                "model": self.name, "messages": messages, "stream": False,
                "options": {"temperature": temperature, "num_ctx": self.context, "num_predict": max_tokens},
            }, self.timeout_s)
            return out["message"]["content"]
        out = _post(f"{self.url}/v1/chat/completions", {
            "model": self.name, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
        }, self.timeout_s)
        return out["choices"][0]["message"]["content"]

    def available(self) -> str | None:
        """None if the model server answers and has the model; otherwise the problem."""
        path = "/api/tags" if self.api == "ollama" else "/v1/models"
        try:
            with urllib.request.urlopen(f"{self.url}{path}", timeout=5) as resp:
                listing = json.loads(resp.read())
        except Exception as e:
            return f"no model server at {self.url} ({e})"
        names = [m.get("name") or m.get("model") or m.get("id") for m in listing.get("models", listing.get("data", []))]
        if not any(n == self.name or (n or "").split(":")[0] == self.name for n in names):
            return f"model {self.name!r} not found on {self.url} (have: {', '.join(filter(None, names)) or 'none'})"
        return None
