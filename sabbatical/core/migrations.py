"""Shared migration runner — used by both the dispatcher daemon and the API server."""

from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def run_migrations(db_path: str):
    alembic_cfg = AlembicConfig()
    alembic_cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    alembic_command.upgrade(alembic_cfg, "head")
