# Georgian AI Accountant

AI-native accounting/tax assistant for Georgian businesses. Chat is the interface; a
deterministic rules engine is the system of record for every number. The AI layer only
turns messages into structured input and explains results the engine already computed.

```
message -> extractor (Claude, or offline keywords) -> intent + facts
        -> rules engine (versioned JSON rules, Decimal math, trace)  -> results
        -> legal index (rad_law Matsne corpus)                        -> cited passages
        -> responder (Claude, or templates; numbers must match engine) -> reply
```

## What's here

| Area | Where | Notes |
|---|---|---|
| Accounts | `app/auth.py`, `app/api/auth.py` | `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`; scrypt passwords, HttpOnly session cookie |
| Domain model | `app/models/` | `User`, `Company` (owned by a user), `CompanyTaxProfile`, `Employee`, `Transaction`, `TaxEvent`, `Conversation`, `Message` |
| CRUD API | `app/api/companies.py` | `/companies/...`, scoped to the signed-in user (others' data returns 404) |
| Conversations | `app/api/conversations.py`, `app/chat/context.py` | Every turn is saved with its full engine output (audit trail); a bare follow-up like "2500" answers the pending question |
| Rules engine | `app/rules/` | Rules are JSON in `app/rules/data/`, versioned by effective date |
| Chat | `app/api/chat.py`, `app/chat/` | `POST /companies/{id}/chat`; test page at `/` |
| Legal citations | `app/legal/`, `app/api/legal.py` | Read-only over rad_law's SQLite FTS5 index; `GET /legal/search` |
| Tax calendar | `app/rules/deadlines.json`, `app/rules/calendar.py`, `app/api/deadlines.py` | Deadlines that apply to the company's profile; done state stored per period |

### Rules and their status

Every result carries `verification`:

- `demo` - placeholder logic, not real law (none shipped any more).
- `unverified` - encoded from the Tax Code text, **not yet reviewed by a qualified
  accountant**. All current rules and deadlines:
  - Salary: 2% pension, 20% income tax, take-home pay, employer cost (Art. 81(1), 82(1)(b³);
    Law on Funded Pension Art. 3(6))
  - VAT registration once 12-month taxable supplies exceed GEL 100 000 (Art. 165(1))
  - VAT on a sale, net or VAT-inclusive (Art. 166)
  - Profit tax on distributions, payout ÷ 0.85 × 15% (Art. 97, 98) and 5% dividend withholding
    (Art. 130)
  - Deadlines: VAT, salary withholding and profit tax returns by the 15th; property tax by 1 April
    and 15 June (Art. 168, 154, 153(10), 205)
- `verified` - set `last_verified_date` on the rule once a professional has checked it
  against the current Matsne consolidated text, including its `effective_from` date.

### AI safeguards

- Claude never computes: the prompt forbids it, and any number in Claude's reply that does
  not appear in the engine results or user message makes the app discard the reply and
  use the template instead (`reply_source: "template"`, with a warning).
- Only the user's message and engine results are sent to the API - no stored records.
- Any API failure, refusal or malformed output falls back to the offline path.

## Run it

```powershell
cp .env.example .env      # then optionally set ANTHROPIC_API_KEY
docker compose up --build
```

- Chat page: http://localhost:8000/ (create an account on first visit)
- API docs: http://localhost:8000/docs

`AI_PROVIDER` picks who reads messages and writes replies:

| `AI_PROVIDER` | Reads messages | Writes replies | Notes |
|---|---|---|---|
| `auto` (default) | Claude if `ANTHROPIC_API_KEY` is set, else keywords | Claude, else templates | |
| `claude` | `ANTHROPIC_MODEL` (default `claude-opus-5`) | Claude, Georgian or English | Paid API |
| `ollama` | local `OLLAMA_MODEL` (default `qwen2.5:14b`) | templates (`OLLAMA_REPLIES=true` to use the model) | Free; nothing leaves the machine; ~7 s per message, ~40 s for the first (model load) |
| `off` | keywords | templates | Fully offline |

On an 8-message English/Georgian probe, qwen2.5:14b classified 8/8 and qwen2.5:7b 6/8. Both wrote
poor Georgian replies, hence templates by default. Whatever the provider, a failed or slow model
call falls back to keywords/templates with a visible warning.

Legal citations need rad_law's index. Compose mounts `LAW_INDEX_DIR`
(default `../rag law/RAD law/data/index`) read-only; without it, results just have no
citations.

The app creates missing tables on startup but does not migrate existing ones. After a
model change, reset the local DB with `docker compose down -v` (or add Alembic).

## Run tests (without Docker)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
```

Tests use in-memory SQLite, a fake Anthropic client and a throwaway legal index - they
never call the real API, whatever is in your environment.

Sessions last `SESSION_DAYS` (default 30). Behind HTTPS, set `SESSION_COOKIE_SECURE=true`.

## Next steps

1. Have a qualified accountant verify every rule and deadline (and their effective dates).
2. Add the Law on Funded Pension to the rad_law corpus so the 2% rate has a quotable excerpt.
3. Input VAT credit (Art. 175-176), small business status (Art. 90), weekend/holiday deadline shifts.
4. Before going public: login rate limiting, password reset, email verification.

Schema changes go through Alembic (`backend/migrations/`); see CLAUDE.md.
