import tomllib
from pathlib import Path
from pydantic import BaseModel
import os

SABBATICAL_DIR = Path.home() / ".sabbatical"
CONFIG_PATH = SABBATICAL_DIR / "config.toml"

class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7420
    db_path: str = str(SABBATICAL_DIR / "sabbatical.db")

class DispatcherConfig(BaseModel):
    polling_interval_ms: int = 500
    max_concurrency: int = 4
    default_max_iterations: int = 50

class LLMConfig(BaseModel):
    openrouter_api_key: str = ""
    default_model: str = "minimax/minimax-m2.7"

class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = str(SABBATICAL_DIR / "logs" / "sabbatical.log")

class SabbaticalConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    dispatcher: DispatcherConfig = DispatcherConfig()
    llm: LLMConfig = LLMConfig()
    logging: LoggingConfig = LoggingConfig()

def load_config() -> SabbaticalConfig:
    if not SABBATICAL_DIR.exists():
        SABBATICAL_DIR.mkdir(parents=True, exist_ok=True)

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

[llm]
openrouter_api_key = "{api_key}"
default_model = "minimax/minimax-m2.7"

[logging]
level = "INFO"
file = "{log_path}"
""".format(
            db_path=str(SABBATICAL_DIR / "sabbatical.db").replace('\\', '\\\\'),
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            log_path=str(SABBATICAL_DIR / "logs" / "sabbatical.log").replace('\\', '\\\\')
        )
        CONFIG_PATH.write_text(default_toml)

    with open(CONFIG_PATH, "rb") as f:
        raw = tomllib.load(f)

    # Handle the fact that we might have missing sections in a newly created or partial config
    return SabbaticalConfig(**raw)
