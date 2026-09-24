"""Ollama backend against a mocked HTTP transport, and provider selection from settings."""

import json

import httpx
import pytest

from app.api import chat as chat_api
from app.chat.llm import AIUnavailable, LLMExtractor
from app.chat.ollama import OllamaBackend
from app.chat.responder import TemplateResponder
from app.config import settings
from app.main import app


def backend_returning(handler) -> OllamaBackend:
    return OllamaBackend("http://ollama:11434/", "qwen2.5:14b", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_ollama_extraction_request_and_parse():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        content = json.dumps({"intent": "check_vat_registration", "amount": "90 000", "language": "ka"})
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    extraction = LLMExtractor(backend_returning(handler)).extract("ბოლო 12 თვის ბრუნვა 90 000 ლარია")

    assert extraction.intent == "check_vat_registration"
    assert extraction.entities == {"taxable_turnover_12m": "90000"}
    assert extraction.source == "ollama"
    assert seen["url"] == "http://ollama:11434/api/chat"
    body = seen["body"]
    assert body["model"] == "qwen2.5:14b" and body["stream"] is False
    assert body["format"]["required"] == ["intent", "amount", "language"]  # schema-constrained output
    assert body["options"]["temperature"] == 0


@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(404, json={"error": "model 'qwen2.5:14b' not found"}),
    lambda r: httpx.Response(200, json={"message": {"content": "not json"}}),
    lambda r: httpx.Response(200, json={"unexpected": True}),
])
def test_ollama_errors_raise_ai_unavailable(handler):
    with pytest.raises(AIUnavailable):
        LLMExtractor(backend_returning(handler)).extract("salary 1000")


def test_ollama_unreachable_raises_ai_unavailable():
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(AIUnavailable, match="not reachable"):
        LLMExtractor(backend_returning(refuse)).extract("salary 1000")


# --- provider selection ---

@pytest.fixture
def config(monkeypatch):
    def apply(**values):
        for key, value in values.items():
            monkeypatch.setattr(settings, key, value)
    return apply


def test_auto_without_key_is_offline(config):
    config(ai_provider="auto", anthropic_api_key="")
    pipeline = chat_api.get_pipeline()
    assert (pipeline.extractor_source, pipeline.responder_source) == ("keyword", "template")


def test_ollama_extracts_but_templates_reply_by_default(config):
    config(ai_provider="ollama", ollama_replies=False, ollama_model="qwen2.5:14b")
    pipeline = chat_api.get_pipeline()
    assert pipeline.extractor_source == "ollama" and pipeline.model == "qwen2.5:14b"
    assert isinstance(pipeline.responder, TemplateResponder)


def test_ollama_replies_opt_in(config):
    config(ai_provider="ollama", ollama_replies=True)
    assert chat_api.get_pipeline().responder_source == "ollama"


def test_chat_falls_back_when_ollama_is_down(client):
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    backend = backend_returning(refuse)
    app.dependency_overrides[chat_api.get_pipeline] = lambda: chat_api.ChatPipeline(
        LLMExtractor(backend), TemplateResponder(), "ollama", "template", backend.model)

    company = client.post("/companies", json={
        "name": "Local LLC", "tax_id": "404777777", "legal_form": "LLC", "registration_date": "2024-01-01",
    }).json()
    body = client.post(f"/companies/{company['id']}/chat", json={"message": "salary 2500", "as_of": "2025-06-01"}).json()
    assert body["extraction"]["source"] == "keyword"
    assert body["results"][0]["amount"] == "300.00"
    assert any("not reachable" in w for w in body["warnings"])
