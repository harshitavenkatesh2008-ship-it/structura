"""Document export and analytics service for Structura.

Provides:
- Markdown export from Document Graph v1.0 with structural tags and provenance comments.
- Block filtering and normalization for TraceBack inspector.
- Real processing analytics computation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from backend.app.models.document_graph import Document, Block


class DocumentExportService:
    """Renders structured document graphs into standard outputs."""

    @staticmethod
    def to_markdown(document: Document) -> str:
        """Convert a Document Graph into clean Markdown representation.

        Preserves reading order across pages and formats headings, lists,
        paragraphs, tables, and images/figures accordingly.
        """
        lines: List[str] = []
        lines.append(f"# {document.filename or document.document_id}")
        lines.append("")

        for page in document.pages:
            lines.append(f"<!-- Page {page.page} -->")
            # Sort blocks by reading order
            sorted_blocks = sorted(page.blocks, key=lambda b: b.reading_order)
            for block in sorted_blocks:
                content = block.content or {}
                b_type = block.type.value if hasattr(block.type, "value") else str(block.type)
                
                # TraceBack provenance anchor
                lines.append(f"<!-- block:{block.id} page:{block.page} bbox:{block.bbox} extractor:{block.extractor} -->")

                if b_type == "heading":
                    text = content.get("text", "").strip()
                    lines.append(f"## {text}")
                    lines.append("")
                elif b_type == "list":
                    text = content.get("text", "").strip()
                    lines.append(f"- {text}")
                    lines.append("")
                elif b_type == "table":
                    headers = content.get("headers", [])
                    rows = content.get("rows", [])
                    if headers:
                        lines.append("| " + " | ".join(str(h) for h in headers) + " |")
                        lines.append("| " + " | ".join("---" for _ in headers) + " |")
                        for row in rows:
                            lines.append("| " + " | ".join(str(c) for c in row) + " |")
                        lines.append("")
                    else:
                        text = content.get("text", "")
                        if text:
                            lines.append(text)
                            lines.append("")
                elif b_type in ("figure", "chart", "image"):
                    title = content.get("title", b_type.capitalize())
                    desc = content.get("description", "")
                    lines.append(f"![{title}]({desc})")
                    lines.append("")
                elif b_type == "equation":
                    latex = content.get("latex") or content.get("raw_text") or content.get("text", "")
                    lines.append(f"$$\n{latex}\n$$")
                    lines.append("")
                else:  # paragraph / fallback
                    text = content.get("text", "").strip()
                    if text:
                        lines.append(text)
                        lines.append("")

        return "\n".join(lines).strip()

    @staticmethod
    def get_blocks(
        document: Document,
        page: Optional[int] = None,
        block_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filter and return structured blocks with normalized bounding boxes."""
        results: List[Dict[str, Any]] = []
        for p in document.pages:
            if page is not None and p.page != page:
                continue
            for b in p.blocks:
                b_type = b.type.value if hasattr(b.type, "value") else str(b.type)
                if block_type is not None and b_type != block_type:
                    continue
                results.append(b.model_dump(mode="json"))
        return results

    @staticmethod
    def compute_analytics(document: Document, pipeline_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Compute document intelligence and extraction quality metrics."""
        total_blocks = 0
        blocks_by_type: Dict[str, int] = {}
        risk_distribution: Dict[str, int] = {"low": 0, "medium": 0, "high": 0}
        total_fidelity = 0.0
        fidelity_count = 0
        extractors_used: Dict[str, int] = {}

        for p in document.pages:
            for b in p.blocks:
                total_blocks += 1
                b_type = b.type.value if hasattr(b.type, "value") else str(b.type)
                blocks_by_type[b_type] = blocks_by_type.get(b_type, 0) + 1
                
                ext = b.extractor or "unknown"
                extractors_used[ext] = extractors_used.get(ext, 0) + 1

                if b.risk:
                    level = b.risk.level.value if hasattr(b.risk.level, "value") else str(b.risk.level)
                    risk_distribution[level] = risk_distribution.get(level, 0) + 1

        if pipeline_result and "block_results" in pipeline_result:
            for br in pipeline_result["block_results"]:
                fid = br.get("fidelity", {})
                if "fidelity_score" in fid:
                    total_fidelity += float(fid["fidelity_score"])
                    fidelity_count += 1

        avg_fidelity = round(total_fidelity / fidelity_count, 4) if fidelity_count > 0 else 1.0

        return {
            "document_id": document.document_id,
            "filename": document.filename,
            "page_count": document.page_count,
            "total_blocks": total_blocks,
            "blocks_by_type": blocks_by_type,
            "risk_distribution": risk_distribution,
            "extractors_used": extractors_used,
            "average_fidelity_score": avg_fidelity,
            "pipeline_status": pipeline_result.get("status", document.status.value) if pipeline_result else document.status.value,
            "metrics": document.metrics.model_dump(mode="json"),
        }
