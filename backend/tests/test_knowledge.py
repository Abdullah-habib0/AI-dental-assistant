"""The knowledge base: reading PDFs, chunking, storing and searching.

These tests never load the real embedding model. A fake embedder turns each word into a
fixed position in a vector, which is crude but enough to test that everything is wired
together correctly. Qdrant runs in memory. So the tests are fast, free and offline.

How well the real model finds the right answers is measured separately (see the eval
work), because that is about quality, not about the code being correct.
"""

import re
import zlib
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from app.core.config import settings
from app.features.knowledge.chunking import chunk_document, split_to_fit
from app.features.knowledge.pdf_reader import ParsedDocument, Section, read_pdf
from app.features.knowledge.service import (
    KnowledgeBase,
    KnowledgeIndexOutdated,
    KnowledgeNotIngested,
    VectorStore,
)

KNOWLEDGE = Path(__file__).resolve().parent.parent / "data" / "knowledge"
PDFS = sorted(KNOWLEDGE.glob("*.pdf"))
SOURCES = KNOWLEDGE / "source"


def words(text: str) -> int:
    return len(text.split())


class FakeEmbedder:
    dimension = 256

    def __init__(self, name: str = "fake-embedder"):
        self.name = name

    def count_tokens(self, text: str) -> int:
        return words(text)

    def embed_documents(self, texts):
        return [self._vector(t) for t in texts]

    def embed_query(self, question):
        return self._vector(question)

    def _vector(self, text):
        vector = [0.0] * self.dimension
        for word in re.findall(r"[a-z]+", text.lower()):
            vector[zlib.crc32(word.encode()) % self.dimension] += 1.0
        length = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / length for v in vector]


def make_knowledge_base(embedder=None, client=None) -> KnowledgeBase:
    store = VectorStore(client or QdrantClient(":memory:"), "test_knowledge")
    return KnowledgeBase(embedder or FakeEmbedder(), store, settings.knowledge_max_chunk_tokens)


def source_sections(pdf: Path) -> dict[str, str]:
    md = (SOURCES / f"{pdf.stem}.md").read_text(encoding="utf-8")
    return dict(re.findall(r"^## (.*?)\n(.*?)(?=^## |\Z)", md, flags=re.M | re.S))


# --- Reading PDFs -------------------------------------------------------------------


def test_the_knowledge_pdfs_exist():
    assert len(PDFS) == 6


@pytest.mark.parametrize("pdf", PDFS, ids=lambda p: p.stem)
def test_every_heading_is_found_in_order(pdf):
    doc = read_pdf(pdf)
    expected = [doc.title] + list(source_sections(pdf))
    assert [s.heading for s in doc.sections] == expected


@pytest.mark.parametrize("pdf", PDFS, ids=lambda p: p.stem)
def test_section_text_matches_the_source_word_for_word(pdf):
    """Nothing lost, nothing added, nothing out of order - and no header or footer."""

    def plain(text):
        return re.sub(r"^(?:- |\d+\. )", "", text, flags=re.M).split()

    sources = source_sections(pdf)
    for section in read_pdf(pdf).sections[1:]:
        if "|" in sources[section.heading]:
            continue  # tables are rewritten as sentences, checked below
        assert plain(section.text) == plain(sources[section.heading]), section.heading


def test_header_and_footer_are_removed():
    for pdf in PDFS:
        for section in read_pdf(pdf).sections:
            assert not re.search(r"\bPage \d+\b", section.text)
            assert not re.search(r"\bv\d+\.\d+\b", section.text)  # footer: "BSD-AC v3.1"


def test_tables_are_rebuilt_one_sentence_per_row():
    doc = read_pdf(KNOWLEDGE / "04_aftercare_instructions.pdf")
    table = next(s for s in doc.sections if s.heading == "What is normal and when to contact us")
    lines = table.text.splitlines()
    # A cell that wrapped onto two lines in the PDF is joined back together.
    assert (
        "Symptom: Sensitivity to cold. Normal for: A few weeks after a filling; a few days after "
        "whitening. Contact Bright Smile Dental if: It is getting worse or lasts more than 4 weeks."
    ) in lines
    assert len([line for line in lines if line.startswith("Symptom:")]) == 6
    # The paragraph after the table is not swallowed into it as a fake row.
    assert lines[-1].startswith("Get emergency help straight away")


def test_lists_keep_their_markers():
    doc = read_pdf(KNOWLEDGE / "05_dental_emergencies.pdf")
    section = next(s for s in doc.sections if s.heading == "Knocked-out adult tooth")
    assert "1. Find the tooth and pick it up by the crown" in section.text
    assert "\n5. Contact Bright Smile Dental or NHS 111 straight away" in section.text


# --- Chunking -----------------------------------------------------------------------


def test_each_section_becomes_one_chunk_with_a_label():
    doc = read_pdf(KNOWLEDGE / "04_aftercare_instructions.pdf")
    chunks = chunk_document(doc, words, max_tokens=400)
    assert len(chunks) == len(doc.sections)
    dry_socket = next(c for c in chunks if c.heading == "Dry socket after a tooth extraction")
    assert dry_socket.labelled_text.startswith("Aftercare Instructions > Dry socket after a tooth extraction\n")


def test_a_long_section_is_split_into_parts_that_fit():
    sentences = [f"Sentence number {i} talks about dental topic {i}." for i in range(60)]
    doc = ParsedDocument("Guide", "guide.pdf", [Section("Long section", " ".join(sentences), [1])])

    chunks = chunk_document(doc, words, max_tokens=60)

    assert len(chunks) > 1
    assert [c.part for c in chunks] == list(range(1, len(chunks) + 1))
    for chunk in chunks:
        assert words(chunk.labelled_text) <= 60
        assert chunk.label.startswith("Guide > Long section")
    # Every sentence survives the split.
    joined = " ".join(c.text for c in chunks)
    assert all(s in joined for s in sentences)


def test_parts_overlap_so_nothing_is_lost_at_a_join():
    lines = [f"Line {i} with a few words in it." for i in range(30)]
    parts = split_to_fit("\n".join(lines), words, budget=40)
    for first, second in zip(parts, parts[1:]):
        assert first.splitlines()[-1] == second.splitlines()[0]


def test_one_huge_sentence_is_still_split():
    giant = " ".join(f"word{i}" for i in range(500))
    parts = split_to_fit(giant, words, budget=50)
    assert all(words(p) <= 50 for p in parts)
    assert " ".join(parts).split() == giant.split()


# --- Storing and searching ----------------------------------------------------------


async def test_ingest_then_search_finds_the_right_section():
    kb = make_knowledge_base()
    per_file = kb.ingest(PDFS)
    assert sum(per_file.values()) == sum(len(read_pdf(p).sections) for p in PDFS)

    results = await kb.search("dry socket bad taste extraction", min_score=0.0)
    assert results[0].heading == "Dry socket after a tooth extraction"
    assert results[0].source == "04_aftercare_instructions.pdf"
    assert results[0].pages
    assert results[0].labelled_text.startswith("Aftercare Instructions > Dry socket")


async def test_nothing_relevant_returns_an_empty_list():
    kb = make_knowledge_base()
    kb.ingest(PDFS)
    assert await kb.search("quantum zebra spaceship", min_score=0.5) == []


async def test_empty_question_returns_nothing():
    assert await make_knowledge_base().search("   ") == []


async def test_search_before_ingest_says_so():
    with pytest.raises(KnowledgeNotIngested):
        await make_knowledge_base().search("anything")


async def test_vectors_from_another_model_are_refused_not_silently_mixed():
    client = QdrantClient(":memory:")
    make_knowledge_base(FakeEmbedder("old-model"), client).ingest(PDFS)

    with pytest.raises(KnowledgeIndexOutdated):
        # Even with a cut-off so high that nothing would pass - this must not quietly
        # come back empty.
        await make_knowledge_base(FakeEmbedder("new-model"), client).search("dry socket", min_score=0.99)


async def test_re_ingesting_replaces_rather_than_duplicates():
    client = QdrantClient(":memory:")
    kb = make_knowledge_base(client=client)
    first = sum(kb.ingest(PDFS).values())
    kb.ingest(PDFS)
    assert VectorStore(client, "test_knowledge").count() == first


async def test_overlong_question_is_refused():
    kb = make_knowledge_base()
    with pytest.raises(ValueError):
        await kb.search("x" * 1001)
