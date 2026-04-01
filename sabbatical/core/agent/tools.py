import os
import subprocess
from pathlib import Path

# Stores pre-edit content for undo support in the editor tool.
_undo_history: dict[str, str] = {}


def _validate_path(workspace: Path, path: str) -> Path:
    """Resolve a path and ensure it stays within the workspace."""
    resolved = (
        (workspace / path).resolve()
        if not os.path.isabs(path)
        else Path(path).resolve()
    )
    if not (str(resolved).startswith(str(workspace) + os.sep) or resolved == workspace):
        raise ValueError(f"Path escapes workspace: {path}")
    return resolved


def create_workspace_tools(workspace_path: str) -> list:
    """Return the five agent tools, each bound to the given workspace."""
    root = Path(workspace_path).resolve()

    def file_read(
        path: str,
        mode: str = "view",
        search_pattern: str = "",
        start_line: int = 0,
        end_line: int = 0,
    ) -> str:
        """Read files from the workspace.

        Modes:
          view   - Display full file content with line numbers.
          lines  - Show a line range (start_line and end_line, 1-indexed).
          search - Search for a regex pattern across files. Set search_pattern.
                   If path is a directory, searches recursively.
          find   - List files and directories at the given path.
        """
        try:
            target = _validate_path(root, path)

            if mode == "view":
                if target.is_dir():
                    entries = sorted(target.iterdir())
                    lines = []
                    for e in entries:
                        prefix = "d " if e.is_dir() else "f "
                        lines.append(prefix + e.name)
                    return "\n".join(lines) if lines else "(empty directory)"
                content = target.read_text()
                numbered = []
                for i, line in enumerate(content.splitlines(), 1):
                    numbered.append(f"{i:>6}\t{line}")
                return "\n".join(numbered)

            elif mode == "lines":
                if not target.is_file():
                    return f"Error: '{path}' is not a file."
                all_lines = target.read_text().splitlines()
                s = max(start_line - 1, 0)
                e = end_line if end_line > 0 else len(all_lines)
                selected = all_lines[s:e]
                numbered = []
                for i, line in enumerate(selected, s + 1):
                    numbered.append(f"{i:>6}\t{line}")
                return "\n".join(numbered) if numbered else "(no lines in range)"

            elif mode == "search":
                if not search_pattern:
                    return "Error: search_pattern is required for search mode."
                try:
                    result = subprocess.run(
                        ["grep", "-rn", "--include=*", search_pattern, str(target)],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=str(root),
                    )
                    output = result.stdout.strip()
                    return (
                        output if output else f"No matches found for '{search_pattern}'"
                    )
                except subprocess.TimeoutExpired:
                    return "Error: Search timed out after 30s."

            elif mode == "find":
                if not target.exists():
                    return f"Error: Path not found: {path}"
                if target.is_file():
                    return str(target)
                entries = sorted(target.rglob("*"))
                lines = []
                for e in entries[:200]:
                    rel = e.relative_to(root)
                    prefix = "d " if e.is_dir() else "f "
                    lines.append(f"{prefix}{rel}")
                result = "\n".join(lines)
                if len(entries) > 200:
                    result += f"\n... and {len(entries) - 200} more"
                return result if result else "(empty directory)"

            else:
                return f"Error: Unknown mode '{mode}'. Use: view, lines, search, find"

        except ValueError as e:
            return f"Error: {e}"
        except FileNotFoundError:
            return f"Error: File not found: {path}"
        except IsADirectoryError:
            return f"Error: '{path}' is a directory. Use mode='view' or mode='find'."
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    def file_write(path: str, content: str) -> str:
        """Write content to a file in the workspace. Creates parent directories if needed."""
        try:
            target = _validate_path(root, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            return f"Written {len(content)} bytes to {path}"
        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    def editor(
        path: str,
        command: str,
        old_str: str = "",
        new_str: str = "",
        line: int = 0,
    ) -> str:
        """Make targeted edits to a file without rewriting the whole thing.

        Commands:
          str_replace - Replace old_str with new_str. old_str must appear exactly once.
          insert      - Insert new_str at the given line number (1-indexed).
          undo_edit   - Revert the last edit to this file.
        """
        try:
            target = _validate_path(root, path)

            if command == "str_replace":
                if not old_str:
                    return "Error: old_str is required for str_replace."
                if not target.is_file():
                    return f"Error: File not found: {path}"
                content = target.read_text()
                count = content.count(old_str)
                if count == 0:
                    return "Error: old_str not found in file."
                if count > 1:
                    return f"Error: old_str appears {count} times. It must be unique. Add more surrounding context."
                _undo_history[str(target)] = content
                new_content = content.replace(old_str, new_str, 1)
                target.write_text(new_content)
                return f"Replaced 1 occurrence in {path}"

            elif command == "insert":
                if not new_str:
                    return "Error: new_str is required for insert."
                if not target.is_file():
                    return f"Error: File not found: {path}"
                content = target.read_text()
                _undo_history[str(target)] = content
                lines = content.splitlines(keepends=True)
                insert_at = max(line - 1, 0)
                insert_text = new_str if new_str.endswith("\n") else new_str + "\n"
                lines.insert(insert_at, insert_text)
                target.write_text("".join(lines))
                return f"Inserted text at line {line} in {path}"

            elif command == "undo_edit":
                key = str(target)
                if key not in _undo_history:
                    return f"Error: No edit history for {path}"
                target.write_text(_undo_history.pop(key))
                return f"Reverted last edit to {path}"

            else:
                return f"Error: Unknown command '{command}'. Use: str_replace, insert, undo_edit"

        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    def shell(command: str, timeout: int = 120) -> str:
        """Execute a shell command in the workspace directory. Returns stdout, stderr, and exit code."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            output += f"\n[exit code: {result.returncode}]"
            return output.strip()
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout}s."

    return [file_read, file_write, editor, shell]


def create_thread_tools(thread_state: dict) -> list:
    """Return the add_comment tool bound to the given thread state.

    The tool writes to thread_state which is read by the worker event loop
    to flush comments to the DB.
    """

    def add_comment(message: str) -> str:
        """Post a comment to the task's comment thread.

        This is the only way to communicate with your team. Your text output
        and reasoning are private; only comments are visible. Post comments
        freely to share findings, document progress, or hand off work.

        Your last comment determines routing — end it with an @tag to hand
        off the task to whoever should go next.

        Args:
            message: The comment to post. Keep it focused — say what matters,
                skip what doesn't. Write as if addressing your team.
        """
        thread_state["pending_comments"].append(message)
        thread_state["comment_count"] += 1
        return "Comment posted to thread."

    return [add_comment]


def create_file_read_tool(workspace_path: str):
    """Return a standalone file_read tool bound to the given workspace.

    Used by the Assistant for read-only workspace access.
    """
    tools = create_workspace_tools(workspace_path)
    return tools[0]  # file_read is first
