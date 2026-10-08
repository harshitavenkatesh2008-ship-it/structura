
"""Convert extractor documents into the canonical C7 Document Graph."""

from backend.app.models import document as source
from backend.app.models import document_graph as target


def to_document_graph(document: source.Document) -> target.Document:
    """Convert an extractor Document into a validated C7 Document."""

    pages = []

    for page in document.pages:
        blocks = []

        for block in page.blocks:
            risk = None

            if block.risk is not None:
                risk = target.Risk(
                    score=block.risk.score,
                    level=block.risk.level.value,
                    signals=list(block.risk.signals),
                )

            blocks.append(
                target.Block(
                    id=block.id,
                    type=block.type.value,
                    page=block.page,
                    bbox=list(block.bbox),
                    reading_order=block.reading_order,
                    content=dict(block.content),
                    extractor=block.extractor.value,
                    risk=risk,
                    confidence=block.confidence,
                    flags=list(block.flags),
                    traceable=block.traceable,
                    parent=block.parent,
                    children=list(block.children),
                )
            )

        pages.append(
            target.Page(
                page=page.page,
                width=page.width,
                height=page.height,
                blocks=blocks,
            )
        )

    metrics = target.Metrics(
        **document.metrics.model_dump()
    )

    return target.Document(
        document_id=document.document_id,
        filename=document.filename,
        format=document.format,
        status=document.status,
        page_count=document.page_count,
        pages=pages,
        metrics=metrics,
    )
