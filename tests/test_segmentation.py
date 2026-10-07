from backend.app.models.document_graph import Document, Page, Block
from backend.app.services.segmentation_service import SegmentationService


def test_empty_document():
    document = Document(document_id="doc_test")
    result = SegmentationService().segment(document)
    assert result.segment_count == 0
    assert result.segments == []


def test_single_paragraph():
    block = Block(
        id="b1",
        type="paragraph",
        page=1,
        bbox=[0.1, 0.2, 0.8, 0.9],
        reading_order=0,
        content={"text": "Hello STRUCTURA"},
    )

    page = Page(
        page=1,
        width=100,
        height=100,
        blocks=[block],
    )

    document = Document(
        document_id="doc_test",
        page_count=1,
        pages=[page],
    )

    result = SegmentationService().segment(document)

    assert result.segment_count == 1
    assert result.segments[0].text == "Hello STRUCTURA"
    assert result.segments[0].source_block_ids == ["b1"]



import pytest
from pydantic import ValidationError

from backend.app.models.segmentation import Segment, SegmentedDocument


def test_reading_order():
    blocks = [
        Block(
            id="b2", type="paragraph", page=1,
            bbox=[0.1, 0.1, 0.8, 0.2],
            reading_order=2,
        ),
        Block(
            id="b1", type="heading", page=1,
            bbox=[0.1, 0.0, 0.8, 0.1],
            reading_order=1,
        ),
    ]

    doc = Document(
        document_id="doc_order",
        page_count=1,
        pages=[Page(page=1, width=100, height=100, blocks=blocks)],
    )

    result = SegmentationService().segment(doc)

    assert [s.source_block_ids[0] for s in result.segments] == ["b1", "b2"]
    assert [s.reading_order for s in result.segments] == [0, 1]


def test_multiple_pages():
    doc = Document(
        document_id="doc_pages",
        page_count=2,
        pages=[
            Page(
                page=2, width=100, height=100,
                blocks=[
                    Block(
                        id="b2", type="paragraph", page=2,
                        bbox=[0.1, 0.1, 0.8, 0.2],
                        reading_order=0,
                    )
                ],
            ),
            Page(
                page=1, width=100, height=100,
                blocks=[
                    Block(
                        id="b1", type="paragraph", page=1,
                        bbox=[0.1, 0.1, 0.8, 0.2],
                        reading_order=0,
                    )
                ],
            ),
        ],
    )

    result = SegmentationService().segment(doc)

    assert [s.page for s in result.segments] == [1, 2]


def test_bbox_preserved():
    bbox = [0.15, 0.25, 0.75, 0.85]

    doc = Document(
        document_id="doc_bbox",
        page_count=1,
        pages=[
            Page(
                page=1, width=100, height=100,
                blocks=[
                    Block(
                        id="b1", type="paragraph", page=1,
                        bbox=bbox,
                        reading_order=0,
                    )
                ],
            )
        ],
    )

    result = SegmentationService().segment(doc)

    assert result.segments[0].bbox == tuple(bbox)


def test_duplicate_segment_ids():
    segment = Segment(
        segment_id="seg_001",
        segment_type="paragraph",
        reading_order=0,
    )

    with pytest.raises(ValidationError):
        SegmentedDocument(
            document_id="doc_duplicate",
            segments=[segment, segment.model_copy()],
            segment_count=2,
        )


def test_original_document_unchanged():
    doc = Document(
        document_id="doc_original",
        page_count=1,
        pages=[
            Page(
                page=1, width=100, height=100,
                blocks=[
                    Block(
                        id="b1", type="paragraph", page=1,
                        bbox=[0.1, 0.1, 0.8, 0.2],
                        reading_order=0,
                    )
                ],
            )
        ],
    )

    before = doc.model_dump()
    SegmentationService().segment(doc)

    assert doc.model_dump() == before


def test_page_mismatch_rejected():
    doc = Document(
        document_id="doc_mismatch",
        pages=[
            Page(
                page=1,
                width=100,
                height=100,
                blocks=[
                    Block(
                        id="b1",
                        type="paragraph",
                        page=2,
                        bbox=[0.1, 0.1, 0.8, 0.2],
                        reading_order=0,
                    )
                ],
            )
        ],
    )

    with pytest.raises(ValueError, match="does not match"):
        SegmentationService().segment(doc)


def test_missing_text():
    doc = Document(
        document_id="doc_no_text",
        pages=[
            Page(
                page=1,
                width=100,
                height=100,
                blocks=[
                    Block(
                        id="b1",
                        type="paragraph",
                        page=1,
                        bbox=[0.1, 0.1, 0.8, 0.2],
                        reading_order=0,
                        content={"other": "value"},
                    )
                ],
            )
        ],
    )

    result = SegmentationService().segment(doc)

    assert result.segments[0].text is None


def test_deterministic_results():
    doc = Document(
        document_id="doc_deterministic",
        pages=[
            Page(
                page=1,
                width=100,
                height=100,
                blocks=[
                    Block(
                        id="b1",
                        type="paragraph",
                        page=1,
                        bbox=[0.1, 0.1, 0.8, 0.2],
                        reading_order=0,
                    )
                ],
            )
        ],
    )

    service = SegmentationService()

    assert service.segment(doc) == service.segment(doc)


def test_invalid_bbox_rejected():
    with pytest.raises(ValidationError):
        Segment(
            segment_id="seg_bad",
            segment_type="paragraph",
            reading_order=0,
            bbox=(0.9, 0.1, 0.2, 0.8),
        )


def test_segment_count_mismatch_rejected():
    with pytest.raises(ValidationError):
        SegmentedDocument(
            document_id="doc_count",
            segments=[],
            segment_count=1,
        )


def test_duplicate_source_block_ids_rejected():
    doc = Document(
        document_id="doc_duplicate_blocks",
        pages=[
            Page(
                page=1,
                width=100,
                height=100,
                blocks=[
                    Block(
                        id="same_id",
                        type="paragraph",
                        page=1,
                        bbox=[0.1, 0.1, 0.8, 0.2],
                        reading_order=0,
                    ),
                    Block(
                        id="same_id",
                        type="paragraph",
                        page=1,
                        bbox=[0.1, 0.3, 0.8, 0.4],
                        reading_order=1,
                    ),
                ],
            )
        ],
    )

    with pytest.raises(ValueError, match="Duplicate source block ID"):
        SegmentationService().segment(doc)


def test_parent_child_relationship_preserved():
    parent = Block(
        id="parent_block",
        type="heading",
        page=1,
        bbox=[0.1, 0.1, 0.8, 0.2],
        reading_order=0,
    )

    child = Block(
        id="child_block",
        type="paragraph",
        page=1,
        bbox=[0.1, 0.3, 0.8, 0.4],
        reading_order=1,
        parent="parent_block",
    )

    doc = Document(
        document_id="doc_hierarchy",
        pages=[
            Page(
                page=1,
                width=100,
                height=100,
                blocks=[parent, child],
            )
        ],
    )

    result = SegmentationService().segment(doc)

    assert result.segments[0].segment_id == "seg_000000"
    assert result.segments[1].parent_id == "seg_000000"
