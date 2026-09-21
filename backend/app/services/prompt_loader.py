"""Load prompt text files from backend/prompts/.

Prompts live in versioned files (extraction_v1.txt, extraction_v2.txt ...)
instead of inside the code, so a prompt change is visible in review, can be
compared run against run in the evaluation, and is recorded in the audit log.
"""

from functools import lru_cache
from pathlib import Path

PROMPTS_DIRECTORY = Path(__file__).resolve().parents[2] / "prompts"


@lru_cache
def load_prompt(prompt_name: str, version: str) -> str:
    """Return the text of prompts/<prompt_name>_<version>.txt."""
    prompt_path = PROMPTS_DIRECTORY / f"{prompt_name}_{version}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path.name}")
    return prompt_path.read_text(encoding="utf-8").strip()
