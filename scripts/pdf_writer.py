"""Small helper that turns simple HTML into a multi-page PDF using PyMuPDF."""

import html
from pathlib import Path

import pymupdf

PAGE_MARGIN_POINTS = 54


def escape_text(text: str) -> str:
    """Escape text so characters like < and & are shown literally in HTML."""
    return html.escape(text, quote=False)


def write_html_to_pdf(html_body: str, output_path: Path) -> None:
    """Lay out the HTML across as many US Letter pages as needed and save it."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    page_rectangle = pymupdf.paper_rect("letter")
    text_area = page_rectangle + (
        PAGE_MARGIN_POINTS,
        PAGE_MARGIN_POINTS,
        -PAGE_MARGIN_POINTS,
        -PAGE_MARGIN_POINTS,
    )

    story = pymupdf.Story(html=html_body, user_css="body { font-size: 11pt; }")
    writer = pymupdf.DocumentWriter(str(output_path))

    has_more_content = True
    while has_more_content:
        device = writer.begin_page(page_rectangle)
        has_more_content, _ = story.place(text_area)
        story.draw(device)
        writer.end_page()

    writer.close()
