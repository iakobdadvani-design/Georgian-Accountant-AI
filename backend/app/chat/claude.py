"""Claude backend for the model-agnostic extractor/responder in app.chat.llm."""

from functools import lru_cache

import anthropic

from app.chat.llm import AIUnavailable, Effort, parse_json
from app.config import settings

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@lru_cache
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60.0, max_retries=2)


class ClaudeBackend:
    name = "claude"

    def __init__(self, client: anthropic.Anthropic, model: str):
        self.client, self.model = client, model

    def complete_json(self, system: str, user: str, schema: dict, effort: Effort) -> dict:
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=8000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            raise AIUnavailable("rate limited") from e
        except anthropic.APIStatusError as e:
            raise AIUnavailable(f"API error {e.status_code}") from e
        except anthropic.APIConnectionError as e:
            raise AIUnavailable("connection error") from e

        if response.stop_reason in ("refusal", "max_tokens"):
            raise AIUnavailable(f"stop_reason={response.stop_reason}")
        return parse_json(next((b.text for b in response.content if b.type == "text"), None))
