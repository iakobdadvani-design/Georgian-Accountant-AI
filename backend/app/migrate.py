"""Bring the database schema up to date on startup.

Databases created before Alembic was added (tables exist, no alembic_version) are stamped at the
baseline revision first, so their data is kept and only later migrations run.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
BASELINE = "0001_baseline"


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["configure_logging"] = False
    return config


def upgrade(engine: Engine) -> None:
    config = alembic_config()
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables and "companies" in tables:
        command.stamp(config, BASELINE)
    command.upgrade(config, "head")
