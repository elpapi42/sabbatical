# Configuration

Sabbatical is configured through a TOML file at `~/.sabbatical/config.toml`. If the file doesn't exist, it's created with defaults on first run.

## Config File Location

```
~/.sabbatical/
├── config.toml          # Configuration file
├── sabbatical.db        # SQLite database
├── server.pid           # API server PID
├── server.log           # Uvicorn process output (stdout/stderr)
├── dispatcher.pid       # Dispatcher PID
├── dispatcher.ready     # Dispatcher ready marker
└── logs/
    ├── api.log          # Structured API server logs
    └── dispatcher.log   # Dispatcher logs
```

## Full Configuration Reference

```toml
[server]
host = "127.0.0.1"        # API server bind address
port = 7420                # API server port
db_path = "~/.sabbatical/sabbatical.db"  # SQLite database path

[dispatcher]
polling_interval_ms = 500           # Task queue poll interval (ms)
max_concurrency = 4                 # Max concurrent agent executions
default_max_iterations = 50         # Default LLM turns per agent run
max_run_duration_seconds = 1800     # Max wall-clock time per run (0 = no limit)

[llm]
openrouter_api_key = ""             # OpenRouter API key (required)
default_model = "minimax/minimax-m2.7"  # Default LLM model

[logging]
level = "INFO"                                      # Log level (DEBUG, INFO, WARNING, ERROR)
api_file = "~/.sabbatical/logs/api.log"             # API server log path
dispatcher_file = "~/.sabbatical/logs/dispatcher.log"  # Dispatcher log path
```

## Section Details

### [server]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `host` | string | `"127.0.0.1"` | Address the API server binds to. Use `"0.0.0.0"` to listen on all interfaces. |
| `port` | integer | `7420` | Port for the API server. |
| `db_path` | string | `"~/.sabbatical/sabbatical.db"` | Path to the SQLite database file. Created automatically if it doesn't exist. |

### [dispatcher]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `polling_interval_ms` | integer | `500` | How often the dispatcher checks for queued tasks. Lower values mean faster task pickup but higher CPU usage. |
| `max_concurrency` | integer | `4` | Maximum number of agent runs executing simultaneously. Each run consumes one worker slot. |
| `default_max_iterations` | integer | `50` | Default limit on LLM turns per agent run. Can be overridden per-agent via `agent edit --max-iterations`. |
| `max_run_duration_seconds` | integer | `1800` | Maximum wall-clock time for a single run (30 minutes default). Set to `0` to disable the timeout. |

### [llm]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `openrouter_api_key` | string | `""` | Your [OpenRouter](https://openrouter.ai) API key. **Required** for agent execution. Can also be set via the `OPENROUTER_API_KEY` environment variable (used during initial config creation). |
| `default_model` | string | `"minimax/minimax-m2.7"` | The LLM model to use when an agent doesn't specify one. Must be a valid OpenRouter model identifier. |

### [logging]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `level` | string | `"INFO"` | Minimum log level. Set to `"DEBUG"` for verbose output during development. |
| `api_file` | string | `"~/.sabbatical/logs/api.log"` | Path to the API server log file. |
| `dispatcher_file` | string | `"~/.sabbatical/logs/dispatcher.log"` | Path to the dispatcher log file. |

Log files use a rotating file handler: 10 MB per file, up to 5 backup files.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | Used to populate `llm.openrouter_api_key` when the config file is first created. After that, edit the config file directly. |

## Model Selection

Models are specified in OpenRouter format: `provider/model-name`.

Examples:
- `minimax/minimax-m2.7` (default)
- `anthropic/claude-3-5-sonnet-20241022`
- `openai/gpt-4o`
- `google/gemini-2.0-flash-exp`

The default model applies to all agents unless overridden per-agent:

```bash
sabbatical agent edit my_agent --organization my_org --model anthropic/claude-3-5-sonnet-20241022
```

To reset an agent back to the default model:

```bash
sabbatical agent edit my_agent --organization my_org --model default
```

## Tuning Tips

### Concurrency

`max_concurrency` controls how many agents can run simultaneously. Higher values process tasks faster but increase:
- OpenRouter API usage (and cost)
- CPU and memory for the dispatcher process
- Database write contention (usually not a bottleneck with WAL mode)

For most single-developer setups, 2-4 is sufficient. Increase if you're running multiple organizations with deep task backlogs.

### Iteration Limits

`default_max_iterations` is a safety net against runaway agents. Most well-instructed agents complete within 10-30 iterations. Set higher (100+) for complex tasks that involve extensive file editing and testing cycles.

Per-agent overrides are useful when different agents have different workload profiles:
- A test writer that runs a full test suite might need more iterations.
- A reviewer that just reads and comments might need fewer.

### Run Timeout

`max_run_duration_seconds` prevents single runs from consuming resources indefinitely. The default of 1800 seconds (30 minutes) works for most tasks. Set to `0` to disable if you have long-running agents that need unlimited time.

### Polling Interval

`polling_interval_ms` controls task pickup latency. The default of 500ms means a queued task waits at most 500ms before being claimed. This is negligible compared to LLM execution time. Lower only if you need sub-second dispatch latency for some reason.
