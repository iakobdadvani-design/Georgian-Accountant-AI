from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/georgian_ai_accountant"

    # Which model reads messages / writes replies. "auto": Claude if a key is set, else offline
    # (keyword extractor + template replies). "ollama" must be chosen explicitly.
    ai_provider: Literal["auto", "claude", "ollama", "off"] = "auto"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    # Local models write poor Georgian and are slow, so by default Ollama only extracts and replies use templates.
    ollama_replies: bool = False

    # Login sessions. Set SESSION_COOKIE_SECURE=true when served over HTTPS.
    session_days: int = 30
    session_cookie_secure: bool = False

    # rad_law's SQLite FTS5 index of Matsne legal texts. Empty -> no legal citations.
    law_index_path: str = ""

    # RS.ge taxpayer lookup: a "service user" created in your eservices.rs.ge account. Empty -> lookup off.
    rs_service_user: str = ""
    rs_service_password: str = ""
    rs_url: str = "https://services.rs.ge/WayBillService/WayBillService.asmx"


settings = Settings()
