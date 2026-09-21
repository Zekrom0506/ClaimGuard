"""Check whether a quote really appears in a piece of text.

Used to verify source sentences from extraction and quotes in citations.
Differences that do not change meaning (line breaks, extra spaces, curly
quotes, letter case) are ignored; any change to the words is not.
"""

import re
import unicodedata

CHARACTER_REPLACEMENTS = {
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
}


def normalize_for_matching(text: str) -> str:
    """Lowercase, unify quotes and dashes, and collapse all whitespace to single spaces."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    for original_character, replacement in CHARACTER_REPLACEMENTS.items():
        normalized = normalized.replace(original_character, replacement)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().strip(".")


def text_contains_quote(text: str, quote: str) -> bool:
    """True if the quote appears in the text, ignoring spacing, case and quote style."""
    normalized_quote = normalize_for_matching(quote)
    if normalized_quote == "":
        return False
    return normalized_quote in normalize_for_matching(text)
