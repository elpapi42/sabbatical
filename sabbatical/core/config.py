import importlib.resources
import logging
import tomllib
from pathlib import Path
from pydantic import BaseModel
import os

logger = logging.getLogger(__name__)

SABBATICAL_DIR = Path.home() / ".sabbatical"
CONFIG_PATH = SABBATICAL_DIR / "config.toml"
SKILL_DIR = SABBATICAL_DIR / "skill"

_SKIP_NAMES = {"__init__.py", "__pycache__"}


def _copy_traversable(source, dest: Path) -> None:
    """Recursively copy an importlib.resources Traversable tree to dest."""
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.name in _SKIP_NAMES or item.name.endswith(".pyc"):
            continue
        target = dest / item.name
        if item.is_file():
            target.write_bytes(item.read_bytes())
        elif item.is_dir():
            _copy_traversable(item, target)


def _ensure_skill_installed() -> None:
    """Copy bundled skill files to ~/.sabbatical/skill/. Silent on failure."""
    try:
        source = importlib.resources.files("sabbatical.skill")
        _copy_traversable(source, SKILL_DIR)
    except Exception:
        logger.debug("Failed to install skill files", exc_info=True)

class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7420
    db_path: str = str(SABBATICAL_DIR / "sabbatical.db")

class DispatcherConfig(BaseModel):
    polling_interval_ms: int = 500
    max_concurrency: int = 4
    default_max_iterations: int = 50
    max_run_duration_seconds: int = 1800  # 30 minutes; 0 = no timeout
    orphan_timeout_seconds: int = 300  # 5 minutes; heartbeats can gap during long LLM calls

class LLMConfig(BaseModel):
    openrouter_api_key: str = ""
    default_model: str = "minimax/minimax-m2.7"

class LoggingConfig(BaseModel):
    level: str = "INFO"
    api_file: str = str(SABBATICAL_DIR / "logs" / "api.log")
    dispatcher_file: str = str(SABBATICAL_DIR / "logs" / "dispatcher.log")

class SabbaticalConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    dispatcher: DispatcherConfig = DispatcherConfig()
    llm: LLMConfig = LLMConfig()
    logging: LoggingConfig = LoggingConfig()

def load_config() -> SabbaticalConfig:
    if not SABBATICAL_DIR.exists():
        SABBATICAL_DIR.mkdir(parents=True, exist_ok=True)

    _ensure_skill_installed()

    if not CONFIG_PATH.exists():
        # Create a default config if it doesn't exist
        default_toml = """[server]
host = "127.0.0.1"
port = 7420
db_path = "{db_path}"

[dispatcher]
polling_interval_ms = 500
max_concurrency = 4
default_max_iterations = 50
max_run_duration_seconds = 1800

[llm]
openrouter_api_key = "{api_key}"
default_model = "minimax/minimax-m2.7"

[logging]
level = "INFO"
api_file = "{api_log_path}"
dispatcher_file = "{dispatcher_log_path}"
""".format(
            db_path=str(SABBATICAL_DIR / "sabbatical.db").replace('\\', '\\\\'),
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            api_log_path=str(SABBATICAL_DIR / "logs" / "api.log").replace('\\', '\\\\'),
            dispatcher_log_path=str(SABBATICAL_DIR / "logs" / "dispatcher.log").replace('\\', '\\\\'),
        )
        CONFIG_PATH.write_text(default_toml)

    with open(CONFIG_PATH, "rb") as f:
        raw = tomllib.load(f)

    # Handle the fact that we might have missing sections in a newly created or partial config
    return SabbaticalConfig(**raw)
