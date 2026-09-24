from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import migrate, models  # noqa: F401 - models registers all tables with Base
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.companies import router as companies_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.api.legal import router as legal_router
from app.api.rules import router as rules_router
from app.database import engine
from app.rules.loader import get_rules

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate.upgrade(engine)
    get_rules()  # fail fast on an invalid rule file
    yield


app = FastAPI(title="Georgian AI Accountant", lifespan=lifespan)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(companies_router)
app.include_router(rules_router)
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(legal_router)


@app.get("/", include_in_schema=False)
def chat_page():
    return FileResponse(STATIC_DIR / "index.html")
