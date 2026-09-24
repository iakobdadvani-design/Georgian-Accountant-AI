"""Claude integration and legal citations, against a fake Anthropic client and a throwaway FTS5 index."""

import json
import sqlite3
from decimal import Decimal
from types import SimpleNamespace

import anthropic
import pytest

from app.api.chat import ChatPipeline, get_pipeline
from app.api.legal import get_legal_index
from app.chat.claude import ClaudeBackend
from app.chat.llm import AIUnavailable, LLMExtractor, LLMResponder, ungrounded_numbers
from app.chat.extractor import Extraction
from app.legal.index import LegalIndex
from app.main import app

VAT_TEXT = ("Article 165 - Registration as a VAT taxpayer\n1. A taxable person shall, unless otherwise provided for "
            "by this Code, from the day when he/she exceeds the total amount of GEL 100 000 for VAT taxable "
            "transactions of supplying goods/providing services carried out during any 12 consecutive calendar "
            "months, within not later than 2 business days, apply to a tax authority for registration as a VAT "
            "taxpayer.")


class FakeClaude:
    """Stands in for anthropic.Anthropic: returns queued JSON payloads (or raises queued exceptions)."""

    def __init__(self, *outputs, stop_reason="end_turn"):
        self.outputs = list(outputs)
        self.stop_reason = stop_reason
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        text = out if isinstance(out, str) else json.dumps(out)
        return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=text)])


# --- extractor ---

def test_claude_extractor_normalizes_amount_and_sends_expected_request():
    fake = FakeClaude({"intent": "calculate_payroll_tax", "amount": "2 500", "language": "en"})
    extraction = LLMExtractor(ClaudeBackend(fake, "claude-opus-5")).extract("hired someone for 2 500 lari")

    assert extraction.entities == {"gross_salary": "2500"}
    assert extraction.source == "claude"
    [call] = fake.calls
    assert call["model"] == "claude-opus-5"
    assert call["fallbacks"] == "default"
    assert call["output_config"]["format"]["type"] == "json_schema"


def test_claude_extractor_discards_non_numeric_amount():
    fake = FakeClaude({"intent": "check_vat_registration", "amount": "about 100k", "language": "en"})
    assert LLMExtractor(ClaudeBackend(fake, "m")).extract("about 100k turnover").entities == {}


def test_language_comes_from_script_not_model():
    fake = FakeClaude({"intent": "calculate_payroll_tax", "amount": None, "language": "en"})
    assert LLMExtractor(ClaudeBackend(fake, "m")).extract("ხელფასი").language == "ka"


@pytest.mark.parametrize("fake", [
    FakeClaude({"intent": "x"}, stop_reason="refusal"),
    FakeClaude("not json"),
    FakeClaude({"intent": "made_up_intent", "amount": None, "language": "en"}),
    FakeClaude(anthropic.APIConnectionError(request=None)),
])
def test_claude_failures_raise_ai_unavailable(fake):
    with pytest.raises(AIUnavailable):
        LLMExtractor(ClaudeBackend(fake, "m")).extract("salary 1000")


# --- grounding guard ---

def test_ungrounded_numbers():
    evidence = '{"amount": "300.00", "citation": "Article 165(1)", "entities": {"gross_salary": "2500"}}'
    assert ungrounded_numbers("Withholding is 300 GEL on 2,500 (Article 165, step 1).", evidence) == set()
    assert ungrounded_numbers("That is about 3,600 GEL a year.", evidence) == {Decimal("3600")}


def test_rate_may_be_restated_as_percentage():
    evidence = '{"trace": ["input.gross_salary (1800) x 0.12 = 216.00"]}'
    assert ungrounded_numbers("That is 12% of 1800, so 216.00.", evidence) == set()
    assert ungrounded_numbers("That is 15% of 1800.", evidence) == {Decimal("15")}


def test_responder_rejects_invented_numbers():
    extraction = Extraction(intent="calculate_payroll_tax", entities={"gross_salary": "2500"})
    fake = FakeClaude({"reply": "You will pay 3600 GEL per year."})
    with pytest.raises(AIUnavailable, match="3600"):
        LLMResponder(ClaudeBackend(fake, "m")).compose("salary 2500", extraction, [])


# --- chat endpoint with Claude ---

@pytest.fixture
def company(client):
    company = client.post("/companies", json={
        "name": "AI LLC", "tax_id": "404333333", "legal_form": "LLC", "registration_date": "2024-01-01",
    }).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": False})
    return company


def use_pipeline(fake):
    backend = ClaudeBackend(fake, "m")
    app.dependency_overrides[get_pipeline] = lambda: ChatPipeline(
        LLMExtractor(backend), LLMResponder(backend), "claude", "claude", "m")


def test_chat_with_claude_reply(client, company):
    use_pipeline(FakeClaude(
        {"intent": "calculate_payroll_tax", "amount": "2500", "language": "ka"},
        {"reply": "საშემოსავლო გადასახადი 490.00 ლარია."},
    ))
    body = client.post(f"/companies/{company['id']}/chat", json={"message": "ხელფასი 2500", "as_of": "2025-06-01"}).json()
    assert body["reply_source"] == "claude"
    assert body["reply"] == "საშემოსავლო გადასახადი 490.00 ლარია."
    assert Decimal(body["results"][0]["amount"]) == Decimal("490.00")  # number came from the engine
    assert body["warnings"] == []


def test_chat_falls_back_to_template_when_reply_invents_numbers(client, company):
    use_pipeline(FakeClaude(
        {"intent": "calculate_payroll_tax", "amount": "2500", "language": "en"},
        {"reply": "You owe 999.99 GEL."},
    ))
    body = client.post(f"/companies/{company['id']}/chat", json={"message": "salary 2500", "as_of": "2025-06-01"}).json()
    assert body["reply_source"] == "template"
    assert "1,960.00 GEL" in body["reply"]
    assert any("999.99" in w for w in body["warnings"])


def test_chat_falls_back_to_keywords_when_extraction_fails(client, company):
    use_pipeline(FakeClaude(anthropic.APIConnectionError(request=None), {"reply": "Income tax is 490.00 GEL."}))
    body = client.post(f"/companies/{company['id']}/chat", json={"message": "salary 2500", "as_of": "2025-06-01"}).json()
    assert body["extraction"]["source"] == "keyword"
    assert body["reply_source"] == "claude"
    assert body["warnings"]


# --- legal index ---

@pytest.fixture
def legal_index(tmp_path):
    path = tmp_path / "laws.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE VIRTUAL TABLE chunks USING fts5(text, title UNINDEXED, url UNINDEXED, language UNINDEXED, "
                   "publication UNINDEXED, fetched_at UNINDEXED, document_id UNINDEXED, tokenize='unicode61')")
        rows = [
            (VAT_TEXT, "TAX CODE OF GEORGIA", "https://matsne.gov.ge/en/document/view/1043717", "en", "", "", "1043717"),
            (VAT_TEXT, "TAX CODE OF GEORGIA", "https://matsne.gov.ge/en/document/view/1043717?p=2", "en", "2", "", "1043717"),
            ("Article 81 - Income tax rate", "TAX CODE OF GEORGIA", "https://x", "en", "", "", "1043717"),
        ]
        db.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    return LegalIndex(path)


def test_legal_search_dedupes_snapshots(legal_index):
    passages = legal_index.search("VAT registration threshold", language="en")
    assert len(passages) == 1
    assert "GEL 100 000" in passages[0].excerpt


def test_legal_search_require_all(legal_index):
    assert legal_index.search("income tax registration", require_all=True) == []


def test_missing_index_endpoint_returns_503(client):
    assert client.get("/legal/search", params={"q": "VAT"}).status_code == 503


def test_chat_attaches_citation(client, company, legal_index):
    app.dependency_overrides[get_legal_index] = lambda: legal_index
    body = client.post(f"/companies/{company['id']}/chat",
                       json={"message": "turnover 150,000 over 12 months", "as_of": "2025-06-01"}).json()
    [result] = body["results"]
    assert result["status"] == "applies"
    [citation] = result["citations"]
    assert "exceeds the total amount of GEL 100 000" in citation["excerpt"]
    assert citation["url"].startswith("https://matsne.gov.ge/")
