
from backend.app.models.document_graph import Document
from backend.app.models.segmentation import Segment, SegmentedDocument


class SegmentationService:
    """Convert Document Graph blocks into ordered, traceable segments."""

    def segment(self, document: Document) -> SegmentedDocument:
        ordered_blocks = []
        seen_block_ids = set()

        for page in document.pages:
            for block in page.blocks:
                if block.page != page.page:
                    raise ValueError(
                        f"Block {block.id} has a page number that "
                        f"does not match its containing page"
                    )

                if block.id in seen_block_ids:
                    raise ValueError(
                        f"Duplicate source block ID: {block.id}"
                    )

                seen_block_ids.add(block.id)
                ordered_blocks.append(block)

        ordered_blocks.sort(
            key=lambda block: (block.page, block.reading_order, block.id)
        )

        block_to_segment = {
            block.id: f"seg_{index:06d}"
            for index, block in enumerate(ordered_blocks)
        }

        segments = []

        for index, block in enumerate(ordered_blocks):
            raw_text = block.content.get("text")
            text = raw_text if isinstance(raw_text, str) else None

            parent_id = (
                block_to_segment.get(block.parent)
                if block.parent is not None
                else None
            )

            segments.append(
                Segment(
                    segment_id=block_to_segment[block.id],
                    segment_type=block.type.value,
                    reading_order=index,
                    page=block.page,
                    parent_id=parent_id,
                    source_block_ids=[block.id],
                    text=text,
                    bbox=tuple(block.bbox),
                )
            )

        return SegmentedDocument(
            document_id=document.document_id,
            segments=segments,
            segment_count=len(segments),
        )
