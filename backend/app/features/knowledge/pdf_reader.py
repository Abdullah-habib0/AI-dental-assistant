"""Reads a PDF back into its structure: sections, paragraphs, bullet points and tables.

Plain PDF text extraction loses all of that - it gives one flat stream of lines. This
reader also looks at each piece of text's font, size and position, which is enough to:

  - drop the header and footer that repeat on every page
  - spot headings (bold, and bigger than the body text)
  - rebuild table rows, which plain extraction returns one cell per line
  - keep bullet points and numbered steps as separate items

It relies on layout, not on how any particular PDF was made, so it works for any
reasonably laid-out document - not just the ones in this project.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

# A separate list marker, e.g. "-", "•", "1." or "2)".
_MARKER = re.compile(r"^(?:[–•\-*]|\d+[.)])$")
# A marker stuck to the start of the text, e.g. "- Do not rinse".
_MARKER_PREFIX = re.compile(r"^(?:([–•\-*])|(\d+)[.)])\s+(.*)$")


@dataclass
class Section:
    heading: str
    text: str
    pages: list[int]


@dataclass
class ParsedDocument:
    title: str
    source: str
    sections: list[Section]


@dataclass
class _Piece:
    x: float
    text: str
    bold: bool
    size: float


@dataclass
class _Line:
    page: int
    y: float  # PDF coordinates: bigger y is higher up the page
    pieces: list[_Piece] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(p.text for p in self.pieces)

    @property
    def size(self) -> float:
        return max(p.size for p in self.pieces)

    @property
    def bold(self) -> bool:
        return all(p.bold for p in self.pieces)


def read_pdf(path: Path) -> ParsedDocument:
    reader = PdfReader(path)
    lines = _drop_repeated(_read_lines(reader), len(reader.pages))
    if not lines:
        raise ValueError(f"{path.name}: no text found. Scanned PDFs need OCR, which isn't supported.")

    body_size = _most_common_size(lines)
    title = (reader.metadata.title if reader.metadata else None) or path.stem
    return ParsedDocument(title=title, source=path.name, sections=_to_sections(lines, body_size, title))


# --- Step 1: every piece of text, with its font, size and position --------------------


def _read_lines(reader: PdfReader) -> list[_Line]:
    lines: list[_Line] = []
    for page_number, page in enumerate(reader.pages, start=1):
        found: list[tuple[float, _Piece]] = []

        def visit(text, cm, tm, font, size, found=found):
            text = " ".join(text.split())  # also turns non-breaking and double spaces into one
            if not text:
                return
            # Where the text really sits: its own position, moved by the page's transform.
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            font_name = str((font or {}).get("/BaseFont", ""))
            found.append((y, _Piece(x, text, "Bold" in font_name, round(size * tm[0], 1))))

        page.extract_text(visitor_text=visit)

        # Pieces at the same height form one line. Top of the page first, left to right.
        found.sort(key=lambda item: (-item[0], item[1].x))
        for y, piece in found:
            last = lines[-1] if lines else None
            if last and last.page == page_number and abs(last.y - y) < 2:
                last.pieces.append(piece)
            else:
                lines.append(_Line(page_number, y, [piece]))

    for line in lines:
        line.pieces.sort(key=lambda p: p.x)
    return lines


def _drop_repeated(lines: list[_Line], page_count: int) -> list[_Line]:
    """Remove headers and footers: lines that turn up on most pages.

    Numbers are ignored when comparing, so "Page 4" and "Page 5" count as the same line.
    """
    if page_count < 3:
        return lines  # too few pages to tell a footer from ordinary text

    def key(line: _Line) -> str:
        return re.sub(r"\d+", "#", line.text.lower())

    pages_seen_on = defaultdict(set)
    for line in lines:
        pages_seen_on[key(line)].add(line.page)
    repeated = {k for k, pages in pages_seen_on.items() if len(pages) > page_count / 2}
    return [line for line in lines if key(line) not in repeated]


def _most_common_size(lines: list[_Line]) -> float:
    """The body text size: the size most of the characters are written in."""
    sizes = Counter()
    for line in lines:
        for piece in line.pieces:
            sizes[piece.size] += len(piece.text)
    return sizes.most_common(1)[0][0]


# --- Step 2: lines -> sections made of paragraphs, list items and tables --------------


def _to_sections(lines: list[_Line], body_size: float, title: str) -> list[Section]:
    sections: list[Section] = []
    heading, blocks, pages = title, [], set()
    i = 0

    def close_section():
        text = "\n".join(_render(b) for b in blocks).strip()
        if text:
            sections.append(Section(heading, text, sorted(pages)))

    while i < len(lines):
        line = lines[i]

        if line.bold and line.size >= body_size + 1.5:
            close_section()
            heading, blocks, pages = line.text, [], {line.page}
            # A long heading can wrap onto a second line.
            while i + 1 < len(lines) and _continues_heading(line, lines[i + 1]):
                i += 1
                heading += " " + lines[i].text
            i += 1
            continue

        if _looks_like_table_row(line):
            table_lines = [line]
            columns = [p.x for p in line.pieces]
            while i + 1 < len(lines) and _belongs_to_table(table_lines[-1], lines[i + 1], columns):
                i += 1
                table_lines.append(lines[i])
            blocks.append(("table", _table_rows(table_lines, columns)))
            pages.update(t.page for t in table_lines)
            i += 1
            continue

        _add_text_line(blocks, line)
        pages.add(line.page)
        i += 1

    close_section()
    return sections


def _continues_heading(first: _Line, nxt: _Line) -> bool:
    return (
        nxt.page == first.page
        and nxt.bold
        and abs(nxt.size - first.size) < 0.5
        and first.y - nxt.y < first.size * 1.6
    )


def _looks_like_table_row(line: _Line) -> bool:
    """Two or more pieces on one line with a wide gap between them are table columns.

    A list marker followed by its text ("-  Do not rinse") is not a table, so a short
    marker at the start of the line is ignored.
    """
    pieces = line.pieces
    if pieces and _MARKER.match(pieces[0].text):
        pieces = pieces[1:]
    if len(pieces) < 2:
        return False
    for left, right in zip(pieces, pieces[1:]):
        estimated_width = len(left.text) * left.size * 0.5
        if right.x - (left.x + estimated_width) < left.size * 2:
            return False
    return True


def _belongs_to_table(previous: _Line, line: _Line, columns: list[float]) -> bool:
    """Still in the table if the line is close below, in the same text size, and every
    piece sits in a column.

    The size check matters: a paragraph straight after a table can start at exactly the
    same position as the first column, but tables are almost always set in their own size.
    """
    if line.page != previous.page or previous.y - line.y > previous.size * 3:
        return False
    if abs(line.size - previous.size) > 0.5:
        return False
    return all(any(abs(p.x - c) < 2 for c in columns) for p in line.pieces)


def _table_rows(lines: list[_Line], columns: list[float]) -> list[list[str]]:
    """Group lines into rows, and pieces into cells.

    A cell that wraps onto several lines has its lines closer together than the gap
    between two rows, so a bigger-than-normal gap means a new row has started.
    """
    rows: list[list[list[str]]] = []
    previous_y = None
    for line in lines:
        if previous_y is None or previous_y - line.y > line.size * 1.6:
            rows.append([[] for _ in columns])
        for piece in line.pieces:
            column = min(range(len(columns)), key=lambda c: abs(columns[c] - piece.x))
            rows[-1][column].append(piece.text)
        previous_y = line.y
    return [[" ".join(cell) for cell in row] for row in rows]


def _add_text_line(blocks: list, line: _Line) -> None:
    pieces = line.pieces
    first = pieces[0].text

    # A list item: a marker as its own piece, or stuck to the front of the text.
    marker, text, indent = None, line.text, pieces[0].x
    if len(pieces) > 1 and _MARKER.match(first):
        marker, text, indent = first, " ".join(p.text for p in pieces[1:]), pieces[1].x
    elif match := _MARKER_PREFIX.match(line.text):
        marker, text = match.group(1) or f"{match.group(2)}.", match.group(3)

    if marker:
        blocks.append(["item", marker, text, indent, line])
        return

    last = blocks[-1] if blocks else None
    # The second line of a list item lines up with that item's text, not its marker.
    if last and last[0] == "item" and abs(last[3] - pieces[0].x) < 2 and _close_below(last[4], line):
        last[2] += " " + text
        last[4] = line
    elif last and last[0] == "para" and abs(last[3] - pieces[0].x) < 2 and _close_below(last[4], line):
        last[2] += " " + text
        last[4] = line
    else:
        blocks.append(["para", None, text, pieces[0].x, line])


def _close_below(previous: _Line, line: _Line) -> bool:
    """The next line of the same paragraph, rather than the start of a new one.

    A page break in the middle of a sentence still counts as the same paragraph. A change
    of text size does not - that is a subtitle, a caption or a note, not more of the same.
    """
    if abs(line.size - previous.size) > 0.5:
        return False
    if line.page != previous.page:
        return not previous.text.rstrip().endswith((".", ":", "!", "?"))
    return 0 < previous.y - line.y < previous.size * 1.6


def _render(block) -> str:
    kind = block[0]
    if kind == "table":
        return "\n".join(_render_table(block[1]))
    if kind == "item":
        marker = block[1]
        return f"{marker} {block[2]}" if marker[0].isdigit() else f"- {block[2]}"
    return block[2]


def _render_table(rows: list[list[str]]) -> list[str]:
    """One sentence per row, with each value labelled by its column heading.

    "Symptom: Numbness. Normal for: 2 to 4 hours..." keeps a row's meaning together, so a
    chunk holding one row still makes sense on its own.
    """
    header, body = rows[0], rows[1:]
    if not body or not all(header):
        return [" | ".join(row) for row in rows]
    out = []
    for row in body:
        if row == header:
            continue  # a header repeated at the top of a new page
        cells = [f"{h}: {v.rstrip('.')}." for h, v in zip(header, row) if v]
        out.append(" ".join(cells))
    return out
