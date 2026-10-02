import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import migrate, models  # noqa: F401 - models registers all tables with Base
from app.api.auth import router as auth_router
from app.api.books import router as books_router
from app.api.chat import router as chat_router
from app.api.companies import router as companies_router
from app.api.conversations import router as conversations_router
from app.api.deadlines import router as deadlines_router
from app.api.employees import router as employees_router
from app.api.health import router as health_router
from app.api.legal import router as legal_router
from app.api.payments import router as payments_router
from app.api.reminders import router as reminders_router
from app.api.reviews import router as reviews_router
from app.api.rsge import company_router as rs_company_router
from app.api.rsge import router as rs_router
from app.api.rules import router as rules_router
from app import reminders
from app.config import settings
from app.database import SessionLocal, engine
from app.notify import email_sender, telegram
from app.rules.calendar import get_deadlines
from app.rules.loader import get_rules

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate.upgrade(engine)
    get_rules()  # fail fast on an invalid rule file
    get_deadlines()
    task = None
    if settings.reminders_enabled and (settings.smtp_host or settings.telegram_bot_token):
        task = asyncio.create_task(reminders.run_forever(
            SessionLocal, email_sender, telegram, settings.reminder_interval_minutes * 60))
    yield
    if task:
        task.cancel()


app = FastAPI(title="Georgian AI Accountant", lifespan=lifespan)

# The page's own script and styles are inline; fonts come from Google Fonts. /docs (Swagger UI) loads its
# assets from a CDN, so it gets the basic headers without the content policy.
CONTENT_POLICY = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
                  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
                  "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
NO_POLICY = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if not request.url.path.startswith(NO_POLICY):
        response.headers.setdefault("Content-Security-Policy", CONTENT_POLICY)
    # The page and its scripts change with each release: browsers must revalidate (a cheap 304) instead of showing
    # a stale copy after an update.
    if request.url.path in ("/", "/app") or request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "no-cache")
    if settings.session_cookie_secure:  # served over HTTPS
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(companies_router)
app.include_router(rules_router)
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(deadlines_router)
app.include_router(legal_router)
app.include_router(rs_router)
app.include_router(rs_company_router)
app.include_router(books_router)
app.include_router(reviews_router)
app.include_router(reminders_router)
app.include_router(payments_router)
app.include_router(employees_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


LANDING_KEYS = ("app.name", "meta.native", "nav.aria", "number.", "lp.", "bank.", "books.outputVat", "books.inputVat")
_landing_cache: dict[tuple[float, float], str] = {}


def landing_html() -> str:
    """landing.html with its texts inlined in all five languages, so the hero paints without waiting for i18n.json."""
    page, catalog_file = STATIC_DIR / "landing.html", STATIC_DIR / "i18n.json"
    key = (page.stat().st_mtime, catalog_file.stat().st_mtime)
    if key not in _landing_cache:
        catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
        texts = {lang: {k: v for k, v in messages.items() if k.startswith(LANDING_KEYS)} for lang, messages in catalog.items()}
        inline = json.dumps(texts, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        html = page.read_text(encoding="utf-8").replace(
            '<script id="catalog" type="application/json">{}</script>',
            f'<script id="catalog" type="application/json">{inline}</script>', 1).replace(
            'content="/static/og.png"', f'content="{settings.public_url.rstrip("/")}/static/og.png"', 1)  # link previews need an absolute URL
        _landing_cache.clear()
        _landing_cache[key] = html
    return _landing_cache[key]


@app.get("/", include_in_schema=False)
def landing_page():
    return HTMLResponse(landing_html())


@app.get("/app", include_in_schema=False)
def chat_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/privacy", include_in_schema=False)
def privacy_page():
    return FileResponse(STATIC_DIR / "privacy.html")
