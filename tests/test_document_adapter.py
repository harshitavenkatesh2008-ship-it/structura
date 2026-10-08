
import pytest
from pydantic import ValidationError

from backend.app.models import document as source
from backend.app.models import document_graph as target
from backend.app.services.document_adapter import to_document_graph


def make_document():
    block = source.Block(
        id="block_1",
        type=source.BlockType.PARAGRAPH,
        page=1,
        bbox=[0.1, 0.2, 0.8, 0.9],
        reading_order=0,
        content={"text": "Hello STRUCTURA"},
        extractor=source.ExtractorType.NATIVE_PDF,
        confidence=0.95,
    )

    page = source.Page(
        page=1,
        width=612,
        height=792,
        blocks=[block],
    )

    return source.Document(
        document_id="doc_1",
        filename="sample.pdf",
        format="pdf",
        page_count=1,
        pages=[page],
    )


def test_converts_to_canonical_document():
    result = to_document_graph(make_document())

    assert isinstance(result, target.Document)
    assert result.document_id == "doc_1"
    assert result.page_count == 1
    assert len(result.pages) == 1


def test_preserves_block_content_and_provenance():
    result = to_document_graph(make_document())
    block = result.pages[0].blocks[0]

    assert block.id == "block_1"
    assert block.type.value == "paragraph"
    assert block.content["text"] == "Hello STRUCTURA"
    assert block.bbox == [0.1, 0.2, 0.8, 0.9]
    assert block.confidence == 0.95


def test_does_not_mutate_source():
    document = make_document()
    before = document.model_dump()

    to_document_graph(document)

    assert document.model_dump() == before


def test_invalid_canonical_bbox_rejected():
    document = make_document()

    # Source validation permits this ordering, but C7 rejects it.
    document.pages[0].blocks[0].bbox = [0.9, 0.2, 0.1, 0.8]

    with pytest.raises(ValidationError):
        to_document_graph(document)
