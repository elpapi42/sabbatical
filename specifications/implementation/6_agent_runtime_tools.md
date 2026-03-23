# Implementation: Agent Runtime Tools

## 9. Agent Runtime (Google ADK Integration)

### `agent/runtime.py`

```python
import uuid
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from sabbatical.agent.tools import create_workspace_tools

def create_agent_runner(
    agent_name: str,
    system_prompt: str,
    model: str,
    openrouter_api_key: str,
    workspace_path: str,
    max_iterations: int,
) -> tuple[Runner, str]:
    """Create an ADK Agent and Runner for a single worker execution."""

    # LiteLLM via OpenRouter
    llm = LiteLlm(
        model=f"openrouter/{model}",
        api_key=openrouter_api_key,
    )

    # Build tools scoped to workspace
    tools = create_workspace_tools(workspace_path)

    agent = Agent(
        name=agent_name,
        model=llm,
        instruction=system_prompt,
        tools=tools,
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="sabbatical",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    session_id = f"run-{uuid.uuid4().hex[:8]}"

    return runner, session_id
```

### Key Design Notes

- **`LiteLlm` direct instantiation** — We pass a `LiteLlm` instance directly to `Agent.model`, bypassing the `LLMRegistry` entirely. This avoids needing to register the `openrouter/` prefix pattern.
- **`InMemorySessionService`** — Each worker execution is ephemeral. We don't need persistent ADK sessions since Sabbatical manages its own state in SQLite.
- **One Agent + Runner per Run** — A fresh Agent and Runner are created for each worker execution. Agents are stateless profiles; the context is injected entirely via `system_prompt` (Blocks A-C) and `user_message` (Block D).

---

## 10. Agent Tools

### `agent/tools.py`

All tools are plain Python functions that are auto-wrapped by ADK into `FunctionTool` instances. Tools accept a `workspace_path` at creation time via closure, confining them to the organization's workspace.

```python
import os
import subprocess
from pathlib import Path

def create_workspace_tools(workspace_path: str) -> list:
    root = Path(workspace_path).resolve()

    def _enforce_path(path: str) -> Path:
        resolved = (root / path).resolve()
        if not str(resolved).startswith(str(root)):
            raise ValueError(f"Path escapes workspace: {path}")
        return resolved

    def read_file(path: str) -> str:
        """Read the contents of a file at the given path relative to the workspace."""
        try:
            target = _enforce_path(path)
            return target.read_text()
        except FileNotFoundError:
            return f"[ERROR] File not found: '{path}'. Use list_directory to see available files."
        except IsADirectoryError:
            return f"[ERROR] '{path}' is a directory, not a file. Use list_directory to see its contents."
        except ValueError as e:
            return f"[ERROR] {e}"

    def write_file(path: str, content: str) -> str:
        """Write content to a file at the given path relative to the workspace.
        Creates parent directories if needed."""
        try:
            target = _enforce_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            return f"Written {len(content)} bytes to {path}"
        except ValueError as e:
            return f"[ERROR] {e}"
        except OSError as e:
            return f"[ERROR] Failed to write '{path}': {e}"

    def list_directory(path: str = ".") -> str:
        """List files and directories at the given path relative to the workspace."""
        try:
            target = _enforce_path(path)
            entries = sorted(target.iterdir())
            lines = []
            for e in entries:
                prefix = "d " if e.is_dir() else "f "
                lines.append(prefix + e.name)
            return "\n".join(lines) if lines else "(empty directory)"
        except FileNotFoundError:
            return f"[ERROR] Directory not found: '{path}'. Use list_directory to see available directories."
        except NotADirectoryError:
            return f"[ERROR] '{path}' is a file, not a directory. Use read_file to read it."
        except ValueError as e:
            return f"[ERROR] {e}"

    def run_command(command: str, timeout_seconds: int = 120) -> str:
        """Execute a shell command in the workspace directory.
        Returns combined stdout and stderr."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            output += f"\n[exit code: {result.returncode}]"
            return output.strip()
        except subprocess.TimeoutExpired:
            return f"[ERROR] Command timed out after {timeout_seconds} seconds: '{command}'"
        except OSError as e:
            return f"[ERROR] Failed to execute command: {e}"

    return [read_file, write_file, list_directory, run_command]
```

---

