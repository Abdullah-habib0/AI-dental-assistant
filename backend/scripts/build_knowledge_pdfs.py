"""Builds the clinic's knowledge-base PDFs from the Markdown files in data/knowledge/source.

The PDFs are what the RAG reads. The Markdown is only how they are written and edited.
After building, every PDF is read back the same way the RAG will read it, and the
script fails if any text comes back broken.

Run it from the backend folder with:   python -m scripts.build_knowledge_pdfs

The Markdown supports only what these documents need:
    key: value lines at the top   ->  title, subtitle, code, version, effective
    ## Heading                    ->  section heading
    - item                        ->  bullet point
    1. item                       ->  numbered step
    | a | b |                     ->  table row (the first row is the header)
    blank line                    ->  new paragraph
"""

import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"
SOURCE_DIR = KNOWLEDGE_DIR / "source"

CLINIC = "Bright Smile Dental"
TEAL = colors.HexColor("#0F6E6E")
LIGHT = colors.HexColor("#E8F3F3")
GREY = colors.HexColor("#5A6B6B")

# Bullets are a dash, not "•". The built-in PDF font stores "•" in a way that comes back
# as a junk character when the text is read out, which would put rubbish in every list
# the RAG reads.
BULLET = "–"

_base = dict(fontName="Helvetica", fontSize=10.5, leading=15, alignment=TA_LEFT)
STYLES = {
    "title": ParagraphStyle("title", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 24, "leading": 29, "textColor": TEAL}),
    "subtitle": ParagraphStyle("subtitle", **{**_base, "fontSize": 13, "leading": 18, "textColor": GREY}),
    "meta": ParagraphStyle("meta", **{**_base, "fontSize": 9, "textColor": GREY}),
    "h2": ParagraphStyle("h2", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 14, "leading": 18, "textColor": TEAL, "spaceBefore": 14, "spaceAfter": 6}),
    "body": ParagraphStyle("body", **{**_base, "spaceAfter": 7}),
    "item": ParagraphStyle("item", **{**_base, "leftIndent": 16, "bulletIndent": 4, "spaceAfter": 3}),
    "cell": ParagraphStyle("cell", **{**_base, "fontSize": 9.5, "leading": 13}),
    "cell_head": ParagraphStyle("cell_head", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 9.5, "leading": 13, "textColor": colors.white}),
    "notice": ParagraphStyle("notice", **{**_base, "fontSize": 9, "leading": 13, "textColor": GREY}),
}


def parse(path: Path) -> tuple[dict, list[tuple]]:
    """Split a source file into its details (title, version...) and a list of blocks."""
    lines = path.read_text(encoding="utf-8").splitlines()

    meta = {}
    while lines and lines[0].strip():
        key, _, value = lines.pop(0).partition(":")
        meta[key.strip()] = value.strip()

    blocks, paragraph, table = [], [], []

    def flush():
        if paragraph:
            blocks.append(("p", " ".join(paragraph)))
            paragraph.clear()
        if table:
            blocks.append(("table", [r[:] for r in table]))
            table.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            flush()
        elif line.startswith("## "):
            flush()
            blocks.append(("h2", line[3:]))
        elif line.startswith("|"):
            if paragraph:
                flush()
            table.append([cell.strip() for cell in line.strip("|").split("|")])
        elif line.startswith("- "):
            flush()
            blocks.append(("bullet", line[2:]))
        elif match := re.match(r"(\d+)\. (.*)", line):
            flush()
            blocks.append(("step", match.group(2), match.group(1)))
        else:
            if table:
                flush()
            paragraph.append(line)
    flush()

    missing = {"title", "subtitle", "code", "version", "effective"} - meta.keys()
    if missing:
        sys.exit(f"{path.name}: missing {', '.join(sorted(missing))} at the top of the file")
    return meta, blocks


def to_flowables(meta: dict, blocks: list[tuple], width: float) -> list:
    story = [
        Paragraph(escape(meta["title"]), STYLES["title"]),
        Spacer(1, 4),
        Paragraph(escape(meta["subtitle"]), STYLES["subtitle"]),
        Spacer(1, 6),
        Paragraph(
            f"Document {escape(meta['code'])} &nbsp;|&nbsp; Version {escape(meta['version'])}"
            f" &nbsp;|&nbsp; Effective {escape(meta['effective'])}",
            STYLES["meta"],
        ),
        Spacer(1, 10),
        _boxed(
            "Sample content: Bright Smile Dental is a fictional practice. This document was "
            "written for a software demonstration and is not medical advice.",
            width,
        ),
        Spacer(1, 6),
    ]

    pending_heading = None
    for block in blocks:
        kind = block[0]
        if kind == "h2":
            pending_heading = Paragraph(escape(block[1]), STYLES["h2"])
            continue

        if kind == "p":
            flowable = Paragraph(escape(block[1]), STYLES["body"])
        elif kind == "bullet":
            flowable = Paragraph(escape(block[1]), STYLES["item"], bulletText=BULLET)
        elif kind == "step":
            flowable = Paragraph(escape(block[1]), STYLES["item"], bulletText=f"{block[2]}.")
        else:
            flowable = _table(block[1], width)

        if pending_heading is not None:
            # Keep a heading on the same page as the first thing under it.
            story.append(KeepTogether([pending_heading, flowable]))
            pending_heading = None
        else:
            story.append(flowable)

    return story


def _boxed(text: str, width: float) -> Table:
    box = Table([[Paragraph(escape(text), STYLES["notice"])]], colWidths=[width])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, TEAL),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return box


def _table(rows: list[list[str]], width: float) -> Table:
    columns = len(rows[0])
    if any(len(row) != columns for row in rows):
        sys.exit(f"Table rows have different numbers of cells: {rows}")

    data = [[Paragraph(escape(c), STYLES["cell_head"]) for c in rows[0]]]
    data += [[Paragraph(escape(c), STYLES["cell"]) for c in row] for row in rows[1:]]

    table = Table(data, colWidths=[width / columns] * columns, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9CFCF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return KeepTogether([Spacer(1, 4), table, Spacer(1, 8)])


def _page_decoration(meta: dict):
    """The header and footer on every page, like a real practice document."""

    def draw(canvas, doc):
        width, height = A4
        canvas.saveState()
        canvas.setStrokeColor(TEAL)
        canvas.setLineWidth(0.6)
        canvas.line(20 * mm, height - 15 * mm, width - 20 * mm, height - 15 * mm)
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.setFillColor(TEAL)
        canvas.drawString(20 * mm, height - 13 * mm, CLINIC)
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(GREY)
        canvas.drawRightString(width - 20 * mm, height - 13 * mm, meta["title"])
        canvas.line(20 * mm, 15 * mm, width - 20 * mm, 15 * mm)
        canvas.drawString(20 * mm, 10 * mm, f"{meta['code']} v{meta['version']}")
        canvas.drawRightString(width - 20 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    return draw


def build(source: Path) -> Path:
    meta, blocks = parse(source)
    target = KNOWLEDGE_DIR / f"{source.stem}.pdf"

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=22 * mm, bottomMargin=22 * mm,
        title=meta["title"], subject=meta["subtitle"], author=CLINIC,
        creator="build_knowledge_pdfs.py",
    )
    decorate = _page_decoration(meta)
    doc.build(to_flowables(meta, blocks, doc.width), onFirstPage=decorate, onLaterPages=decorate)
    return target


def check(pdf: Path) -> tuple[int, int]:
    """Read the PDF back exactly as the RAG will, and refuse broken text."""
    reader = PdfReader(pdf)
    text = "\n".join(page.extract_text() for page in reader.pages)
    broken = sorted({ch for ch in text if ch in "�\x7f" or (ord(ch) < 32 and ch not in "\n\t")})
    if broken:
        sys.exit(f"{pdf.name}: text comes back with broken characters {[hex(ord(c)) for c in broken]}")
    if not reader.metadata or reader.metadata.title is None:
        sys.exit(f"{pdf.name}: missing PDF title")
    return len(reader.pages), len(text.split())


def main() -> None:
    sources = sorted(SOURCE_DIR.glob("*.md"))
    if not sources:
        sys.exit(f"No Markdown files found in {SOURCE_DIR}")

    total_pages = total_words = 0
    for source in sources:
        pdf = build(source)
        pages, words = check(pdf)
        total_pages += pages
        total_words += words
        print(f"  {pdf.name:44} {pages:2} pages  {words:5} words")
    print(f"  {'TOTAL':44} {total_pages:2} pages  {total_words:5} words")


if __name__ == "__main__":
    main()
