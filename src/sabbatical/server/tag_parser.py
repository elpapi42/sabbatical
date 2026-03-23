import re

TAG_PATTERN = re.compile(r"@([a-z][a-z0-9_]*)\b")


def extract_all_tags(text: str) -> list[str]:
    """Extract all @tag candidates from text in order of appearance.

    Returns tag names without the @ prefix. Only matches lowercase
    snake_case identifiers (matching the agent naming convention).
    """
    return TAG_PATTERN.findall(text)


def resolve_first_valid_tag(text: str, valid_names: set[str]) -> tuple[str | None, list[str]]:
    """Extract all tags, then return the first one that appears in valid_names.

    Returns (first_valid_tag_or_None, all_extracted_tags).
    The caller uses all_extracted_tags to distinguish "no tags at all"
    from "tags present but none valid".
    """
    all_tags = extract_all_tags(text)
    for tag in all_tags:
        if tag in valid_names:
            return tag, all_tags
    return None, all_tags
