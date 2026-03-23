# Implementation: Configuration

## 3. Configuration

### File Location
`~/.sabbatical/config.toml`

### Schema

```toml
[server]
host = "127.0.0.1"
port = 7420
db_path = "~/.sabbatical/sabbatical.db"

[dispatcher]
polling_interval_ms = 500
max_concurrency = 4
default_max_iterations = 50

[llm]
openrouter_api_key = "sk-or-..."
default_model = "anthropic/claude-sonnet-4-20250514"
assistant_model = "anthropic/claude-sonnet-4-20250514"
```

### `config.py`

```python
from pathlib import Path
from pydantic import BaseModel
import tomllib

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
    openrouter_api_key: str
    default_model: str = "anthropic/claude-sonnet-4-20250514"
    assistant_model: str = "anthropic/claude-sonnet-4-20250514"

class SabbaticalConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    dispatcher: DispatcherConfig = DispatcherConfig()
    llm: LLMConfig

def load_config() -> SabbaticalConfig:
    with open(CONFIG_PATH, "rb") as f:
        raw = tomllib.load(f)
    return SabbaticalConfig(**raw)
```

---

