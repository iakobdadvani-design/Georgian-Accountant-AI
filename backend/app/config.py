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

    # Emails (comma-separated) of qualified accountants allowed to sign off rules and deadlines.
    reviewer_emails: str = ""

    @property
    def reviewers(self) -> set[str]:
        return {e.strip().lower() for e in self.reviewer_emails.split(",") if e.strip()}

    # Deadline reminders. Email over SMTP (port 465 = SSL, otherwise STARTTLS); Telegram via a bot from @BotFather.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    telegram_bot_token: str = ""
    reminder_interval_minutes: int = 60
    reminders_enabled: bool = True  # the background loop; tests never start it

    # RS.ge taxpayer lookup: a "service user" created in your eservices.rs.ge account. Empty -> lookup off.
    rs_service_user: str = ""
    rs_service_password: str = ""
    rs_url: str = "https://services.rs.ge/WayBillService/WayBillService.asmx"


settings = Settings()
