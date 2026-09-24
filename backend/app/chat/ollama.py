"""Local Ollama backend for the model-agnostic extractor/responder in app.chat.llm. Nothing leaves the machine."""

import httpx

from app.chat.llm import AIUnavailable, Effort, parse_json

# The first request after startup loads the model into memory, which can take a while on CPU.
TIMEOUT_SECONDS = 180.0


class OllamaBackend:
    name = "ollama"

    def __init__(self, base_url: str, model: str, client: httpx.Client | None = None):
        self.base_url, self.model = base_url.rstrip("/"), model
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    def complete_json(self, system: str, user: str, schema: dict, effort: Effort) -> dict:
        try:
            response = self.client.post(f"{self.base_url}/api/chat", json={
                "model": self.model,
                "stream": False,
                "format": schema,  # constrained decoding to the JSON schema
                "options": {"temperature": 0},
                "keep_alive": "30m",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            })
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise AIUnavailable("local model timed out") from e
        except httpx.HTTPStatusError as e:
            raise AIUnavailable(f"Ollama error {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise AIUnavailable("Ollama not reachable") from e
        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as e:
            raise AIUnavailable("unexpected Ollama response") from e
        return parse_json(content)
