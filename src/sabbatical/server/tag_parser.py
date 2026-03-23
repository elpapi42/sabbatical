import re

TAG_PATTERN = re.compile(r"@([a-z][a-z0-9_]*)\b")


def parse_first_tag(text: str) -> str | None:
    """Extract the first valid @tag from text. Returns the name without @, or None."""
    match = TAG_PATTERN.search(text)
    return match.group(1) if match else None
