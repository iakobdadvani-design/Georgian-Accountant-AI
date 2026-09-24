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
| `books/`, `api/books.py`, `static/books.js` | Sales & expenses: sums of recorded transactions (`books/__init__.py`), bank statement import (CSV/.xlsx, `books/importer.py`), monthly summary running the VAT registration / VAT payable / small business rules on those sums |
| `facts.py` | `company_facts`: the `company.*` facts rules see |
| `i18n/` | Reply catalogs `messages/<lang>.json`, `t()`/`tplural()`, locale number/date formatting |
| `static/index.html`, `static/i18n.json` | The whole UI (vanilla JS, no build) and its catalog (all visible text) |

## Commands

```powershell
docker compose up -d --build      # app on http://localhost:8000 (UI) and /docs (API)
cd backend; .\.venv\Scripts\python -m pytest -q -p no:warnings   # tests: SQLite, fake AI, no network
```

Schema changes go through Alembic (see "Database" below).

## Rules in the app (unverified until an accountant signs them off)

| Rule / deadline | Law |
|---|---|
| `ge.payroll.income_tax` — 2% pension, 20% income tax, take-home, employer cost | Tax Code 81(1), 82(1)(b3); Funded Pension law 3(6) (from Matsne, not in the corpus) |
| `ge.vat.registration_threshold` — register once 12-month taxable supplies > GEL 100 000 | 165(1) |
| `ge.vat.output_vat` — VAT on a net price, or 18/118 of a VAT-inclusive one | 166 |
| `ge.vat.payable` — output VAT minus deductible input VAT; `max` step keeps payable and the refundable excess at 0 or more | 174-176, 181(1) |
| `ge.profit.distribution` — payout / 0.85 x 15% | 97(1), 97(10), 98(1) |
| `ge.dividend.withholding` — 5% to individuals, none to companies | 130(1)-(2) |
| `ge.small_business.tax` — individual entrepreneur with small business status: 1%, or 3% once the year's gross income passes GEL 500 000 | 88(1), 90(1)-(2) |
| Deadlines: VAT (15th), salary withholding (15th), profit tax return (15th), property tax (1 Apr, 15 Jun), small business return (15th), micro business return (31 Mar) | 168(1), 154(3)-(4), 153(10), 205(2)-(4), 93(1¹), 93(1) |
| Deadline on a weekend or Labour Code holiday → next working day (`rules/workdays.py`, Orthodox Easter computed) | 3(2), 3(6); Labour Code 30(1) |

Chat intents (`chat/extractor.py`): `calculate_payroll_tax`, `check_vat_registration`, `calculate_vat`,
`calculate_distribution`, `calculate_small_business_tax`, `calculate_vat_payable` (two amounts: `SECOND_AMOUNT_FACT`), `list_deadlines`, `unknown`. Each has an amount fact in `INTENT_AMOUNT_FACT`
(except deadlines), keyword group(s) in priority order, answer phrasing in `responder.py`, and a field
in the LLM extraction schema. Defaults the chat assumes (and says it assumed) live in `DEFAULT_FACTS`
in `api/chat.py`: pension participation, dividend to an individual, small business under the GEL 500 000 limit.

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
  with worked examples. Real rules stay `last_verified_date: null` in the files. A qualified
  accountant signs them off in the app's Rule review screen (`api/reviews.py`, `reviews.py`): only
  emails in `REVIEWER_EMAILS` can, each decision stores who/credentials/when and a hash of the exact
  rule content, and editing a rule afterwards turns it back to unverified. Never set
  `last_verified_date` or create reviews yourself. Any new place that returns `RuleResult`s must pass
  them through `reviews.apply_to_results` so sign-offs show.
- **Source rules from the Tax Code text** in the rad_law corpus (or Matsne), not from memory or
  secondary guides. `C:\Users\iakob\Desktop\rag law\RAD law\data\index\laws.sqlite3`.
- **Money is `Decimal`**, rounded half-up to 0.01 only where a step says so. Never floats.
- **Georgian strings are written by Claude**; flag new ones for native-speaker review.
- Match surrounding code: small functions, few comments, type hints, no new dependencies unless needed.

## Answer quality (evals)

`backend/evals/cases.json`: ~50 questions in all five languages with the expected intent, facts, rule
result (status/amount) and reply language. `python -m evals.run [--provider ollama|claude] [--model-replies]`
scores a pipeline; `tests/test_evals.py` requires the offline pipeline to pass every case not marked
`"hard"` (casual phrasings only a model is expected to get). Add a case for every bug found in a real
conversation. Grounding is checked only for model-written replies.

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

## Sales & expenses (books)

Transactions store the total paid/received (`amount`, VAT included) and `vat_amount`. Books code only
adds amounts up; any tax figure is a rule evaluated with those sums (`api/books.py: summary`). Legal
limits are read from the rule files (`rule_threshold()` for condition values, `TaxRule.limits` for
others), never hard-coded; only the 80% "approaching" warning share is an app setting. VAT inside an
amount always comes from `ge.vat.output_vat` (`books.vat_inside`). Imported rows get a SHA-256
fingerprint (`external_id`, unique per company) so re-imports add nothing. The chat fills
`taxable_turnover_12m` / `over_small_business_limit` from the books when the user doesn't state them
(`with_books` in `api/chat.py`) and says so (`Extraction.from_books`). `static/books.js` is a second
script that reuses the page's globals; the page calls it only through `window.Books?.…`.

## Reminders

`reminders.py` runs as a background task (started in `main.py` lifespan only when SMTP or Telegram is
configured): every minute it polls the Telegram bot for `/start <code>` links, every
`REMINDER_INTERVAL_MINUTES` it sends due reminders. Dates come from `deadline_items`; `reminder_log`
(unique per user/company/deadline/channel) makes sending idempotent, and a failed delivery isn't logged, so
it's retried next round. Tests use `send_due`/`link_telegram` with fake senders and override
`get_email`/`get_telegram`; they never start the loop (TestClient without `with` skips lifespan).

## RS.ge lookup

`GET /rs/taxpayers/{tin}` (9 or 11 digits) asks services.rs.ge for the registered name and VAT status;
the add-company and tax-profile dialogs use it to fill the form. It needs an RS "service user"
(`RS_SERVICE_USER` / `RS_SERVICE_PASSWORD` in `.env`), created by the taxpayer in eservices.rs.ge;
without one the endpoint answers 503 "not set up". Never ask for or store a user's RS portal login,
and don't scrape rs.ge pages. RS data only pre-fills facts the user then saves; it never feeds a
calculation directly. Tests override `get_rs_client` and must never call RS.

## Going public

- Sign-in, sign-up and reset are rate-limited in memory (`ratelimit.py`, cleared per test in `conftest`).
  Per process: fine for the single-process deployment, move to Redis before running several.
- Password reset: `POST /auth/password-reset` always answers 202 (never reveals accounts) and emails a
  1-hour single-use link (`PUBLIC_URL/#reset=<token>`, only its SHA-256 stored); confirming signs out every
  session. Needs SMTP; without it the page hides "Forgot password?".
- Security headers and a Content-Security-Policy come from middleware in `main.py` (not on `/docs`,
  which loads Swagger from a CDN). Anything the page loads from a new origin must be added there.
- Production: `deploy/docker-compose.prod.yml` (Caddy for HTTPS, only 80/443 open, no `--reload`,
  secure cookies). Backups: the `backup` service dumps nightly into `./backups` (git-ignored).
- `static/privacy.html` is a draft for a lawyer; don't present it as reviewed.

## Gotchas (Windows dev box)

- The local venv is Python 3.14, the container 3.12. 3.14 evaluates annotations lazily, so a missing
  import used only in a type hint passes local tests and crashes the container on startup. Run
  `docker compose exec -w /app backend python -m pytest -q` (Git Bash: prefix `MSYS_NO_PATHCONV=1`)
  before calling a change done.

- Git Bash heredocs mangle `\b`, `\n` and quotes inside inline Python. Write patch scripts to a
  file (Write tool) or edit files directly instead of `python -c "..."` with escapes.
- There's no local Node; syntax-check the page's JS with `docker run node:20-alpine node --check`.
- Paths contain spaces (`rag law/RAD law`); quote them.
- Verify UI changes in a real browser (Playwright) — tests don't cover the page. Allow ~60 s for
  the first chat reply when `AI_PROVIDER=ollama` (the model loads on first use).
