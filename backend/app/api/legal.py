from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.legal.index import LegalIndex
from app.rules.schema import Passage, RuleResult

router = APIRouter(prefix="/legal", tags=["legal"])


def get_legal_index() -> LegalIndex | None:
    index = LegalIndex(settings.law_index_path) if settings.law_index_path else None
    return index if index and index.available else None


def attach_citations(results: list[RuleResult], index: LegalIndex | None) -> list[RuleResult]:
    """Look up each rule's supporting passage. Evidence only; the results' numbers are untouched."""
    if index is None:
        return results
    cited = []
    for result in results:
        source = result.legal_source
        passages = []
        if source.search_query:
            passages = index.search(source.search_query, limit=1, language=source.language,
                                    document_id=source.document_id, require_all=True)
        cited.append(result.model_copy(update={"citations": passages}))
    return cited


@router.get("/search", response_model=list[Passage])
def search(
    q: str = Query(min_length=2, max_length=500),
    language: Literal["en", "ka"] | None = None,
    document_id: str | None = None,
    limit: int = Query(default=4, ge=1, le=8),
    index: LegalIndex | None = Depends(get_legal_index),
):
    if index is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Legal index not configured (LAW_INDEX_PATH)")
    return index.search(q, limit=limit, language=language, document_id=document_id)
