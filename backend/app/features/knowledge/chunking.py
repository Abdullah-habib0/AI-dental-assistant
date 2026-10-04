"""Splits parsed documents into chunks for searching.

  1. By structure: one section becomes one chunk. The documents' own headings already
     mark where one topic ends and the next begins.
  2. Recursive, as a safety net: a section too long for the embedding model is split at
     lines, then sentences, then words - whichever is needed - with a small overlap so
     that nothing is lost at a join.
  3. A context label on every chunk ("Document > Heading"), so a chunk that just says
     "Do not rinse your mouth" still carries what it is about.

Sizes are counted in the embedding model's own tokens. The model only reads its first
512 tokens and silently ignores the rest, so measuring in words or characters could let
the end of a chunk go unsearchable without anyone noticing.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.features.knowledge.pdf_reader import ParsedDocument

CountTokens = Callable[[str], int]

# The overlap repeats the last piece of one part at the start of the next, but only if
# that piece is small. Repeating a huge piece would just make two near-identical chunks.
_MAX_OVERLAP_SHARE = 0.25


@dataclass
class Chunk:
    document: str
    source: str
    heading: str
    text: str
    pages: list[int]
    part: int  # 1 for most chunks; 2, 3... when a long section had to be split

    @property
    def label(self) -> str:
        return f"{self.document} > {self.heading}" + (f" (part {self.part})" if self.part > 1 else "")

    @property
    def labelled_text(self) -> str:
        """What gets embedded and shown to the LLM: the label, then the text."""
        return f"{self.label}\n{self.text}"


def chunk_document(doc: ParsedDocument, count_tokens: CountTokens, max_tokens: int) -> list[Chunk]:
    chunks = []
    for section in doc.sections:
        # Room for the label is taken off first, so label + text always fits.
        label_tokens = count_tokens(f"{doc.title} > {section.heading} (part 99)\n")
        budget = max_tokens - label_tokens
        if budget < 20:
            raise ValueError(f"{doc.source}: heading '{section.heading}' is too long to leave room for text")

        for part, text in enumerate(split_to_fit(section.text, count_tokens, budget), start=1):
            chunks.append(Chunk(doc.title, doc.source, section.heading, text, section.pages, part))
    return chunks


def split_to_fit(text: str, count_tokens: CountTokens, budget: int) -> list[str]:
    """Return `text` as one piece if it fits, otherwise as several pieces that each fit."""
    if count_tokens(text) <= budget:
        return [text]

    parts, current = [], []
    for piece in _small_pieces(text, count_tokens, budget):
        if current and count_tokens("\n".join(current + [piece])) > budget:
            parts.append("\n".join(current))
            overlap = current[-1]
            small_enough = count_tokens(overlap) <= budget * _MAX_OVERLAP_SHARE
            current = [overlap, piece] if small_enough else [piece]
            if count_tokens("\n".join(current)) > budget:
                current = [piece]
        else:
            current.append(piece)
    if current:
        parts.append("\n".join(current))
    return parts


def _small_pieces(text: str, count_tokens: CountTokens, budget: int) -> list[str]:
    """Break text into pieces that each fit: lines first, then sentences, then words."""
    pieces = []
    for line in text.split("\n"):
        if count_tokens(line) <= budget:
            pieces.append(line)
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            if count_tokens(sentence) <= budget:
                pieces.append(sentence)
                continue
            words: list[str] = []
            for word in sentence.split():
                if words and count_tokens(" ".join(words + [word])) > budget:
                    pieces.append(" ".join(words))
                    words = [word]
                else:
                    words.append(word)
            if words:
                pieces.append(" ".join(words))
    return pieces
