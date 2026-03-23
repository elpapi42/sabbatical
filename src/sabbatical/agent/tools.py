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

    def list_directory(path: str = ".") -> str:
        """List files and directories at the given path relative to the workspace."""
        try:
            target = _enforce_path(path)
            if not target.exists():
                return f"[ERROR] Directory not found: '{path}'. Use list_directory('.') to see the workspace root."
            if not target.is_dir():
                return f"[ERROR] '{path}' is a file, not a directory."
            entries = sorted(target.iterdir())
            lines = []
            for e in entries:
                prefix = "d " if e.is_dir() else "f "
                lines.append(prefix + e.name)
            return "\n".join(lines) if lines else "(empty directory)"
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
            return f"[ERROR] Command timed out after {timeout_seconds}s: '{command}'"

    return [read_file, write_file, list_directory, run_command]
