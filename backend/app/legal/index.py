"""Read-only access to rad_law's SQLite FTS5 index of Matsne legal texts.

Retrieval only: passages are shown as evidence next to engine results; nothing here feeds a calculation.
"""

import re
import sqlite3
from contextlib import closing
from pathlib import Path

from app.rules.schema import Passage

STOP_WORDS = {"a", "an", "and", "as", "for", "in", "is", "of", "on", "or", "the", "to", "what", "when", "which"}
EXCERPT_CHARS = 700


class LegalIndexUnavailable(RuntimeError):
    pass


def match_expression(query: str, require_all: bool) -> str | None:
    words = list(dict.fromkeys(w for w in re.findall(r"\w+", query.lower()) if w not in STOP_WORDS))[:40]
    if not words:
        return None
    return (" AND " if require_all else " OR ").join(f'"{w}"' for w in words)


def excerpt(text: str, query: str) -> str:
    """The window of the chunk holding the most distinct query words, so the relevant sentence is visible.

    Chunks are ~1800 chars and often begin mid-way through an unrelated article.
    """
    lowered = text.lower()
    words = {w for w in re.findall(r"\w+", query.lower()) if w not in STOP_WORDS}
    hits = sorted((m.start(), m.group(0)) for m in re.finditer(r"\w+", lowered) if m.group(0) in words)

    best_start, best_score = 0, 0
    for i, (pos, _) in enumerate(hits):
        in_window = {w for p, w in hits[i:] if p < pos + EXCERPT_CHARS}
        if len(in_window) > best_score:
            best_start, best_score = pos, len(in_window)

    # Back up to the start of the line so the excerpt opens on a paragraph/article boundary.
    line_start = lowered.rfind("\n", 0, best_start) + 1
    start = line_start if best_start - line_start < 300 else best_start
    snippet = text[start:start + EXCERPT_CHARS].strip()
    return ("..." if start else "") + snippet + ("..." if start + EXCERPT_CHARS < len(text) else "")


class LegalIndex:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @property
    def available(self) -> bool:
        return self.path.is_file()

    def search(
        self,
        query: str,
        *,
        limit: int = 3,
        language: str | None = None,
        document_id: str | None = None,
        require_all: bool = False,
    ) -> list[Passage]:
        if not self.available:
            raise LegalIndexUnavailable(f"Legal index not found at {self.path}")
        expression = match_expression(query, require_all)
        if expression is None:
            return []

        clauses, params = ["chunks MATCH ?"], [expression]
        for column, value in (("language", language), ("document_id", document_id)):
            if value:
                clauses.append(f"{column} = ?")
                params.append(value)

        with closing(sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)) as db:
            rows = db.execute(
                "SELECT rowid, text, title, url, language, publication FROM chunks WHERE "
                + " AND ".join(clauses)
                + " ORDER BY bm25(chunks) LIMIT ?",
                [*params, limit * 5],
            ).fetchall()

        passages, seen = [], set()
        for rowid, text, title, url, lang, publication in rows:
            if text in seen:  # the same passage recurs across publication snapshots
                continue
            seen.add(text)
            passages.append(Passage(chunk_id=rowid, title=title, url=url, publication=publication or "",
                                    language=lang, excerpt=excerpt(text, query)))
            if len(passages) == limit:
                break
        return passages
