import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal, Protocol

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.companies import get_company
from app.api.legal import attach_citations, get_legal_index
from app.api.rules import company_facts
from app.auth import get_current_user
from app.chat.claude import ClaudeBackend, get_client
from app.chat.context import apply_context, inherit_language, pending_state, topic_state
from app.chat.extractor import INTENT_AMOUNT_FACT, Extraction, Extractor, KeywordExtractor
from app.chat.llm import AIUnavailable, LLMExtractor, LLMResponder
from app.chat.ollama import OllamaBackend
from app.chat.responder import TemplateResponder, compose_reply, missing_questions, suggestions_for
from app.config import settings
from app.database import get_db
from app.legal.index import LegalIndex
from app.models import Company, Conversation, Message, User
from app.models.enums import MessageRole
from app.rules.engine import evaluate, referenced_facts
from app.rules.loader import get_rules
from app.rules.schema import RuleResult

log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

TITLE_CHARS = 60

# Facts filled in when the user doesn't say, and always disclosed in the reply. Most employees are
# auto-enrolled in the funded pension scheme (Law on Funded Pension, Art. 3).
DEFAULT_FACTS: dict[str, dict[str, bool | str]] = {
    "calculate_payroll_tax": {"pension_participant": True},
    # Small-company dividends usually go to the owner personally (Tax Code Art. 130(1)).
    "calculate_distribution": {"dividend_recipient": "individual"},
}


def with_defaults(extraction: Extraction) -> Extraction:
    defaults = {k: v for k, v in DEFAULT_FACTS.get(extraction.intent, {}).items() if k not in extraction.entities}
    if not defaults:
        return extraction
    return extraction.model_copy(update={"entities": {**extraction.entities, **defaults},
                                         "assumed": [*extraction.assumed, *defaults]})


class Responder(Protocol):
    def compose(self, message: str, extraction: Extraction, results: list[RuleResult]) -> str: ...


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    as_of: date = Field(default_factory=date.today)
    conversation_id: uuid.UUID | None = Field(default=None, description="Omit to start a new conversation")


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    reply_source: Literal["claude", "ollama", "template"]
    extraction: Extraction
    used_context: bool = Field(default=False, description="True when an earlier turn supplied intent or facts")
    results: list[RuleResult]
    questions: list[str] = Field(default=[], description="Follow-up questions for facts the engine still needs")
    suggestions: list[str] = Field(default=[], description="Example questions to offer when the turn wasn't a tax question")
    warnings: list[str] = []


@dataclass
class ChatPipeline:
    extractor: Extractor
    responder: Responder
    extractor_source: Literal["claude", "ollama", "keyword"]
    responder_source: Literal["claude", "ollama", "template"]
    model: str | None = None


def get_pipeline() -> ChatPipeline:
    provider = settings.ai_provider
    if provider == "auto":
        provider = "claude" if settings.anthropic_api_key else "off"
    if provider == "claude":
        backend = ClaudeBackend(get_client(), settings.anthropic_model)
        return ChatPipeline(LLMExtractor(backend), LLMResponder(backend), "claude", "claude", backend.model)
    if provider == "ollama":
        backend = OllamaBackend(settings.ollama_url, settings.ollama_model)
        if settings.ollama_replies:
            return ChatPipeline(LLMExtractor(backend), LLMResponder(backend), "ollama", "ollama", backend.model)
        return ChatPipeline(LLMExtractor(backend), TemplateResponder(), "ollama", "template", backend.model)
    return ChatPipeline(KeywordExtractor(), TemplateResponder(), "keyword", "template")


class ChatStatus(BaseModel):
    ai_enabled: bool
    provider: Literal["claude", "ollama"] | None
    model: str | None
    replies: Literal["claude", "ollama", "template"]
    legal_index: bool


@router.get("/chat/status", response_model=ChatStatus)
def chat_status(
    pipeline: ChatPipeline = Depends(get_pipeline), legal_index: LegalIndex | None = Depends(get_legal_index)
):
    provider = pipeline.extractor_source if pipeline.extractor_source in ("claude", "ollama") else None
    return ChatStatus(ai_enabled=provider is not None, provider=provider, model=pipeline.model,
                      replies=pipeline.responder_source, legal_index=legal_index is not None)


def open_conversation(db: Session, user: User, company: Company, payload: ChatRequest) -> Conversation:
    if payload.conversation_id is None:
        title = payload.message.strip().replace("\n", " ")
        conversation = Conversation(user_id=user.id, company_id=company.id,
                                    title=title[:TITLE_CHARS] + ("…" if len(title) > TITLE_CHARS else ""))
        db.add(conversation)
        db.flush()
        return conversation
    conversation = db.get(Conversation, payload.conversation_id)
    if conversation is None or conversation.user_id != user.id or conversation.company_id != company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


def last_assistant_payload(conversation: Conversation) -> dict:
    for message in reversed(conversation.messages):
        if message.role == MessageRole.assistant:
            return message.payload or {}
    return {}


@router.post("/companies/{company_id}/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    company: Company = Depends(get_company),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    pipeline: ChatPipeline = Depends(get_pipeline),
    legal_index: LegalIndex | None = Depends(get_legal_index),
):
    conversation = open_conversation(db, user, company, payload)
    warnings: list[str] = []
    try:
        extraction = pipeline.extractor.extract(payload.message)
    except AIUnavailable as e:
        log.warning("%s extraction failed, using keywords: %s", pipeline.extractor_source, e)
        warnings.append(f"AI extraction unavailable ({e}); used keyword matching.")
        extraction = KeywordExtractor().extract(payload.message)
    previous = last_assistant_payload(conversation)
    pending = previous.get("pending")
    extraction = inherit_language(extraction, payload.message, (previous.get("extraction") or {}).get("language"))
    extraction, used_context = apply_context(extraction, payload.message, pending, previous.get("topic"))
    extraction = with_defaults(extraction)

    results: list[RuleResult] = []
    if extraction.intent != "unknown":
        topic_fact = f"input.{INTENT_AMOUNT_FACT[extraction.intent]}"
        rules = [r for r in get_rules() if topic_fact in referenced_facts(r)]
        facts = company_facts(company, db) | {f"input.{k}": v for k, v in extraction.entities.items()}
        results = attach_citations(evaluate(rules, facts, payload.as_of), legal_index)

    reply_source = pipeline.responder_source
    try:
        reply = pipeline.responder.compose(payload.message, extraction, results)
    except AIUnavailable as e:
        log.warning("%s reply failed, using template: %s", pipeline.responder_source, e)
        warnings.append(f"AI reply unavailable ({e}); used template.")
        reply, reply_source = compose_reply(extraction, results, payload.message), "template"

    questions = missing_questions(results, extraction.language)
    response = ChatResponse(conversation_id=conversation.id, reply=reply, reply_source=reply_source,
                            extraction=extraction, used_context=used_context, results=results,
                            questions=questions, suggestions=suggestions_for(extraction, payload.message),
                            warnings=warnings)

    record = response.model_dump(mode="json", exclude={"conversation_id"})
    record["as_of"] = payload.as_of.isoformat()
    # A turn the engine couldn't act on ("hi", "thanks") keeps an unanswered question open.
    missing = list(dict.fromkeys(f for r in results for f in r.missing_facts))
    record["pending"] = pending_state(extraction, missing) or (pending if extraction.intent == "unknown" else None)
    record["topic"] = topic_state(extraction) or (previous.get("topic") if extraction.intent == "unknown" else None)
    db.add_all([
        Message(conversation_id=conversation.id, role=MessageRole.user, content=payload.message),
        Message(conversation_id=conversation.id, role=MessageRole.assistant, content=reply, payload=record),
    ])
    conversation.updated_at = datetime.now(UTC)
    db.commit()
    return response
