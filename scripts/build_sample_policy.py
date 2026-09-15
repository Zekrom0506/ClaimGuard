"""Build the synthetic sample policy PDF from its Markdown source.

Usage: python scripts/build_sample_policy.py
"""

from pathlib import Path

from pdf_writer import escape_text, write_html_to_pdf

POLICIES_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "policies"
SOURCE_FILE = POLICIES_DIRECTORY / "sample_lumbar_mri_policy.md"
OUTPUT_FILE = POLICIES_DIRECTORY / "sample_lumbar_mri_policy.pdf"


def markdown_to_simple_html(markdown_text: str) -> str:
    """Convert the few Markdown features the policy uses (# headings, paragraphs) to HTML."""
    html_parts = []
    for line in markdown_text.splitlines():
        stripped_line = line.strip()
        if stripped_line == "":
            continue
        if stripped_line.startswith("## "):
            html_parts.append(f"<h2>{escape_text(stripped_line[3:])}</h2>")
        elif stripped_line.startswith("# "):
            html_parts.append(f"<h1>{escape_text(stripped_line[2:])}</h1>")
        else:
            html_parts.append(f"<p>{escape_text(stripped_line)}</p>")
    return "\n".join(html_parts)


def main() -> None:
    """Read the Markdown policy and write it out as a PDF."""
    markdown_text = SOURCE_FILE.read_text(encoding="utf-8")
    write_html_to_pdf(markdown_to_simple_html(markdown_text), OUTPUT_FILE)
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
