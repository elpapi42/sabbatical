from strands_tools.file_read import file_read
from strands_tools.file_write import file_write
from strands_tools.editor import editor
from strands_tools.shell import shell
from strands_tools.think import think


def create_workspace_tools(workspace_path: str) -> list:
    """Return the strands-agents-tools configured for the given workspace.

    The shell tool gets work_dir set to the workspace path.
    Other tools operate on absolute paths — agents are instructed
    via system prompt to work within the workspace.
    """
    return [file_read, file_write, editor, shell, think]
