"""Helpers for putting untrusted document text into prompts safely."""

import re

# Any tag that looks like one of the tags our prompts use to fence off data.
FENCE_TAG_PATTERN = re.compile(
    r"<\s*/?\s*(request_document|policy_excerpt|case_details)[^>]*>",
    re.IGNORECASE,
)


def remove_fence_tags(untrusted_text: str) -> str:
    """Remove our own tag names from document text.

    Without this, a document containing "</request_document>" could close the
    data section early and make the rest of its text look like instructions.
    """
    return FENCE_TAG_PATTERN.sub("[tag removed]", untrusted_text)


def wrap_untrusted_text(tag_name: str, untrusted_text: str, attributes: str = "") -> str:
    """Put text inside <tag_name> ... </tag_name> after neutralising fake tags."""
    opening_tag = f"<{tag_name}{' ' + attributes if attributes else ''}>"
    return f"{opening_tag}\n{remove_fence_tags(untrusted_text)}\n</{tag_name}>"
