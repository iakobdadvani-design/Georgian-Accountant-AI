# Georgian AI Accountant

Chat-first tax assistant for Georgian small businesses. FastAPI + PostgreSQL backend, a single-file
chat page, and a deterministic rules engine. Fully available in Georgian, English, Russian, German and
French (interface, replies, rules, deadlines).

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
| `rules/engine.py` | Pure evaluation: tri-state conditions (True / False / missing fact), Decimal math, trace, `steps` calculations with a breakdown |
| `rules/deadlines.json`, `rules/calendar.py` | Filing/payment deadlines; applicability uses the same conditions as rules |
| `rules/schema.py` | Rule/result models; `LocalizedText` = `str` or `{"en": ..., "ka": ...}` |
| `chat/extractor.py` | Intents, keyword extractor, amount parsing |
| `chat/llm.py` | Model-agnostic extractor/responder + grounding check; `claude.py`, `ollama.py` are backends |
| `chat/responder.py` | Template replies (answer-first, en + ka), follow-up questions, small talk |
| `chat/context.py` | Multi-turn: pending question carried across turns, language inheritance |
| `api/` | Routes. Everything under `/companies`, `/conversations` is scoped to the signed-in user |
| `legal/index.py` | Read-only search over rad_law's Matsne SQLite FTS5 index (citations only) |
| `rsge.py`, `api/rsge.py` | RS.ge taxpayer lookup (name + VAT-payer status for a tax ID) via the official WayBillService SOAP API |
| `i18n/` | Reply catalogs `messages/<lang>.json`, `t()`/`tplural()`, locale number/date formatting |
| `static/index.html`, `static/i18n.json` | The whole UI (vanilla JS, no build) and its catalog (all visible text) |

## Commands

```powershell
docker compose up -d --build      # app on http://localhost:8000 (UI) and /docs (API)
cd backend; .\.venv\Scripts\python -m pytest -q -p no:warnings   # tests: SQLite, fake AI, no network
```

Schema changes go through Alembic (see "Database" below).

## Rules in the app (all "unverified")

| Rule / deadline | Law |
|---|---|
| `ge.payroll.income_tax` — 2% pension, 20% income tax, take-home, employer cost | Tax Code 81(1), 82(1)(b3); Funded Pension law 3(6) (from Matsne, not in the corpus) |
| `ge.vat.registration_threshold` — register once 12-month taxable supplies > GEL 100 000 | 165(1) |
| `ge.vat.output_vat` — VAT on a net price, or 18/118 of a VAT-inclusive one | 166 |
| `ge.profit.distribution` — payout / 0.85 x 15% | 97(1), 97(10), 98(1) |
| `ge.dividend.withholding` — 5% to individuals, none to companies | 130(1)-(2) |
| Deadlines: VAT (15th), salary withholding (15th), profit tax return (15th), property tax (1 Apr, 15 Jun) | 168(1), 154(3)-(4), 153(10), 205(2)-(4) |

Chat intents (`chat/extractor.py`): `calculate_payroll_tax`, `check_vat_registration`, `calculate_vat`,
`calculate_distribution`, `list_deadlines`, `unknown`. Each has an amount fact in `INTENT_AMOUNT_FACT`
(except deadlines), keyword group(s) in priority order, answer phrasing in `responder.py`, and a field
in the LLM extraction schema. Defaults the chat assumes (and says it assumed) live in `DEFAULT_FACTS`
in `api/chat.py`: pension participation, dividend to an individual.

## Languages (ka, en, ru, de, fr)

- **No user-visible string in code.** Replies: `app/i18n/messages/<lang>.json` via `t(key, lang)`.
  UI: `static/i18n.json`, via `data-i18n*` attributes in markup and `t()` in the page script. Rule and
  deadline texts are `{"ka","en","ru","de","fr"}` maps inside the rule files. Tests fail if any
  language lacks a key or a placeholder (`test_i18n.py`, `test_ui_catalog.py`).
- **Numbers and dates are formatted per language, never hand-written**: `format_amount` /
  `format_date` / `format_month` on the server; `formatAmount` / `shortDate` / `monthYear` in the page
  (catalog-driven; don't switch back to `Intl` date/number formatting, it lacks Georgian in some builds).
  en `1,960.00`, de `1.960,00`, ka/ru `1 960,00` (no-break space), fr `1 960,00` (narrow no-break).
- **Plurals**: plural maps in catalogs (`{"one","few","many"}` for Russian, `{"one","other"}` en/de/fr,
  `{"other"}` ka) via `tplural()` / `tp()`.
- **Reply language**: Georgian or Cyrillic script decides; otherwise clear Latin-language hints; otherwise
  the user's chosen interface language (`ChatRequest.language`, else `users.language`).
- **Keywords** for each intent exist in all five languages (`chat/extractor.py`); a trailing `$` marks
  a whole-word keyword. Amount parsing is locale-independent (`2.500` = `2,500` = `2 500`).
- Translations are Claude's: flag new ones for native-speaker review, especially tax terminology.

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
  After changing a model: `docker compose exec -w /app backend alembic revision --autogenerate
  -m "..." --rev-id 000N_name`, review the file, then restart. **Name every constraint in the model
  first** (`UniqueConstraint(..., name="uq_...")`): uvicorn `--reload` applies a new migration as soon
  as the file appears, so an unnamed constraint lands with a Postgres-chosen name. Finish with
  `alembic check` (must say "No new upgrade operations detected").

## AI providers

`AI_PROVIDER` in `.env`: `auto` (Claude if `ANTHROPIC_API_KEY`, else offline), `claude`, `ollama`
(local, currently qwen2.5:14b: good at extraction, poor Georgian prose, so replies default to
templates), `off`. Any model failure falls back to keywords/templates with a visible warning.
Tests override the pipeline and must never call a real model.

## RS.ge lookup

`GET /rs/taxpayers/{tin}` (9 or 11 digits) asks services.rs.ge for the registered name and VAT status;
the add-company and tax-profile dialogs use it to fill the form. It needs an RS "service user"
(`RS_SERVICE_USER` / `RS_SERVICE_PASSWORD` in `.env`), created by the taxpayer in eservices.rs.ge;
without one the endpoint answers 503 "not set up". Never ask for or store a user's RS portal login,
and don't scrape rs.ge pages. RS data only pre-fills facts the user then saves; it never feeds a
calculation directly. Tests override `get_rs_client` and must never call RS.

## Gotchas (Windows dev box)

- Git Bash heredocs mangle `\b`, `\n` and quotes inside inline Python. Write patch scripts to a
  file (Write tool) or edit files directly instead of `python -c "..."` with escapes.
- There's no local Node; syntax-check the page's JS with `docker run node:20-alpine node --check`.
- Paths contain spaces (`rag law/RAD law`); quote them.
- Verify UI changes in a real browser (Playwright) — tests don't cover the page. Allow ~60 s for
  the first chat reply when `AI_PROVIDER=ollama` (the model loads on first use).
