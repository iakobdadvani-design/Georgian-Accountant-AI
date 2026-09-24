# Georgian AI Accountant

Chat-first tax assistant for Georgian small businesses. FastAPI + PostgreSQL backend, a single-file
chat page, and a deterministic rules engine. Users write in Georgian or English.

## The one rule that shapes everything

**The AI never calculates.** A model (Claude, a local Ollama model, or keyword matching) only
(1) turns a message into an intent + facts and (2) phrases the engine's result. Every amount,
threshold and yes/no comes from `app/rules/` and is reproducible from the rule file, the facts and
the date. Model replies are rejected if they contain a number the engine didn't produce
(`ungrounded_numbers` in `app/chat/llm.py`). Don't weaken that check to make a reply pass.

## Layout (backend/app)

| Path | What |
|---|---|
| `rules/data/*.json` | Tax rules: versioned by `effective_from/to`, with conditions, calculation, legal source |
| `rules/engine.py` | Pure evaluation: tri-state conditions (True / False / missing fact), Decimal math, trace |
| `rules/schema.py` | Rule/result models; `LocalizedText` = `str` or `{"en": ..., "ka": ...}` |
| `chat/extractor.py` | Intents, keyword extractor, amount parsing |
| `chat/llm.py` | Model-agnostic extractor/responder + grounding check; `claude.py`, `ollama.py` are backends |
| `chat/responder.py` | Template replies (answer-first, en + ka), follow-up questions, small talk |
| `chat/context.py` | Multi-turn: pending question carried across turns, language inheritance |
| `api/` | Routes. Everything under `/companies`, `/conversations` is scoped to the signed-in user |
| `legal/index.py` | Read-only search over rad_law's Matsne SQLite FTS5 index (citations only) |
| `static/index.html` | The whole UI (vanilla JS, no build). Georgian/English labels in the `UI` object |

## Commands

```powershell
docker compose up -d --build      # app on http://localhost:8000 (UI) and /docs (API)
cd backend; .\.venv\Scripts\python -m pytest -q -p no:warnings   # tests: SQLite, fake AI, no network
```

Schema changes go through Alembic (see "Database" below).

## Conventions

- **Replies answer first**, like an accountant: "No, you don't need to register. <why>", or the
  amount, then the reason, then what's needed next. The legal source is a footnote in the result
  card, never the answer. Reply in the language the user wrote in; a bare number ("2500") keeps the
  conversation's language.
- **Every new rule** needs: a legal source (article + Matsne URL, `search_query` for the excerpt),
  `if_false` explanations on its conditions (en + ka), answer phrasing in `responder.py`, and tests
  with worked examples. Real rules stay `last_verified_date: null` (shown as "Unverified") until a
  qualified accountant signs off; never set it yourself.
- **Source rules from the Tax Code text** in the rad_law corpus (or Matsne), not from memory or
  secondary guides. `C:\Users\iakob\Desktop\rag law\RAD law\data\index\laws.sqlite3`.
- **Money is `Decimal`**, rounded half-up to 0.01 only where a step says so. Never floats.
- **Georgian strings are written by Claude**; flag new ones for native-speaker review.
- Match surrounding code: small functions, few comments, type hints, no new dependencies unless needed.

## Database

- The local Postgres holds the owner's **real account and data**. Never run `docker compose down -v`,
  drop tables, or delete rows you didn't create. Test accounts use `@example.com`; delete only those.
- Migrations: `backend/migrations/` (Alembic). The app runs `alembic upgrade head` on startup.
  After changing a model: `alembic revision --autogenerate -m "..."` inside the backend container,
  review the file, then restart.

## AI providers

`AI_PROVIDER` in `.env`: `auto` (Claude if `ANTHROPIC_API_KEY`, else offline), `claude`, `ollama`
(local, currently qwen2.5:14b: good at extraction, poor Georgian prose, so replies default to
templates), `off`. Any model failure falls back to keywords/templates with a visible warning.
Tests override the pipeline and must never call a real model.

## Gotchas (Windows dev box)

- Git Bash heredocs mangle `\b`, `\n` and quotes inside inline Python. Write patch scripts to a
  file (Write tool) or edit files directly instead of `python -c "..."` with escapes.
- There's no local Node; syntax-check the page's JS with `docker run node:20-alpine node --check`.
- Paths contain spaces (`rag law/RAD law`); quote them.
- Verify UI changes in a real browser (Playwright) — tests don't cover the page.
