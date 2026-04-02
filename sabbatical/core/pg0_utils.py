"""pg0 URI helpers — DSN rewriting and URI file management."""

from pathlib import Path

from sabbatical.core.config import SABBATICAL_DIR
from sabbatical.core.exceptions import SabbaticalError

PG0_URI_PATH = SABBATICAL_DIR / "pg0.uri"


def async_dsn_from_pg0_uri(uri: str) -> str:
    """postgresql://... → postgresql+asyncpg://..."""
    return uri.replace("postgresql://", "postgresql+asyncpg://", 1)


def sync_dsn_from_pg0_uri(uri: str) -> str:
    """postgresql://... → postgresql+psycopg2://..."""
    return uri.replace("postgresql://", "postgresql+psycopg2://", 1)


def write_pg0_uri(uri: str) -> None:
    PG0_URI_PATH.parent.mkdir(parents=True, exist_ok=True)
    PG0_URI_PATH.write_text(uri)


def read_pg0_uri() -> str:
    try:
        return PG0_URI_PATH.read_text().strip()
    except FileNotFoundError:
        raise SabbaticalError(
            "Database not available — the dispatcher is not running. "
            "Run a sabbatical command to start it automatically, "
            "or run 'sabbatical status' to check."
        )
