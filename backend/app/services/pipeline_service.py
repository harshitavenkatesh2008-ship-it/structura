
"""C11 integration: extraction, Document Graph, routing, and fidelity."""

from pathlib import Path
from typing import Any

from backend.app.extractors.base import NativePDFExtractor
from backend.app.extractors.registry import (
    ExtractorRegistry,
    build_default_registry,
)
from backend.app.models.document_graph import Document
from backend.app.services.document_adapter import to_document_graph
from backend.app.services.fidelity import determine_escalation
from backend.app.services.router import evidence_from_block, route_region
from backend.app.validators.fidelity import calculate_fidelity


class PipelineService:
    """Run native PDF extraction and evaluate each document block."""

    def __init__(
        self,
        extractor: Any = None,
        registry: ExtractorRegistry | None = None,
    ) -> None:
        self.extractor = (
            extractor if extractor is not None else NativePDFExtractor()
        )
        self.registry = (
            registry if registry is not None else build_default_registry()
        )

    def process(self, file_path: str | Path) -> dict[str, Any]:
        # 1. Extract the PDF using the available native extractor.
        extracted = self.extractor.extract(file_path)

        # 2. Convert extraction results into the canonical Document Graph.
        document: Document = to_document_graph(extracted)

        results: list[dict[str, Any]] = []

        # 3. Run SAFE Router and FidelityGuard for each block.
        for page in document.pages:
            for block in page.blocks:
                block_data = block.model_dump(mode="json")

                # Determine whether native PDF extraction produced
                # usable text for this particular block.
                #
                # Use serialized values so string-backed enums are
                # handled consistently.
                block_type = block_data.get("type")
                extractor_name = block_data.get("extractor")

                content = block_data.get("content") or {}
                native_text = (
                    content.get("text")
                    if isinstance(content, dict)
                    else None
                )

                has_native_text = (
                    extractor_name == "native_pdf"
                    and block_type in {"heading", "paragraph", "list"}
                    and isinstance(native_text, str)
                    and bool(native_text.strip())
                )

                # Pass verified extraction evidence to SAFE Router.
                #
                # Do not assume native text exists for image,
                # scanned, or empty-text blocks.
                evidence_kwargs = {}

                if has_native_text:
                    evidence_kwargs = {
                        "native_text_available": True,
                        "insufficient_native_text": False,
                        "scanned_or_image_only": False,
                    }

                evidence = evidence_from_block(
                    block_data,
                    **evidence_kwargs,
                )

                route = route_region(evidence)

                # FidelityGuard evaluates the current extraction.
                fidelity = calculate_fidelity(block_data)

                # FidelityGuard recommends any follow-up action.
                escalation = determine_escalation(
                    block_data,
                    fidelity,
                )

                # Specialist extraction is not implemented in
                # this integration. Never claim it was executed.
                route_executed = False

                # A route different from the initial extractor
                # requires an additional extraction capability.
                requires_specialist = (
                    route.route != extractor_name
                )

                resolved = self.registry.resolve_status(
                    route.route,
                    extractor_name,
                )

                route_status = (
                    "unsupported"
                    if resolved == "unsupported"
                    else (
                        "already_satisfied"
                        if resolved == "already_satisfied"
                        else resolved
                    )
                )

                results.append(
                    {
                        "block_id": block.id,
                        "page": block.page,
                        "initial_extractor": extractor_name,
                        "route": route.route,
                        "route_reason": route.reason_code,
                        "route_is_fallback": route.is_fallback,
                        "route_executed": route_executed,
                        "route_status": route_status,
                        "requires_specialist": requires_specialist,
                        "fidelity": fidelity,
                        "escalation": escalation,
                    }
                )

        # 4. Determine aggregate pipeline status.
        #
        # Passing FidelityGuard alone is insufficient if
        # a required specialist route remains unexecuted.

        actions = [
            result["fidelity"]["action"]
            for result in results
        ]

        unexecuted_routes = [
            result
            for result in results
            if result["requires_specialist"]
            and not result["route_executed"]
        ]

        if not results:
            status = "review"
        elif any(action == "escalate" for action in actions):
            status = "escalate"
        elif any(action == "review" for action in actions):
            status = "review"
        elif unexecuted_routes:
            status = "review"
        else:
            status = "accept"

        return {
            "document": document,
            "status": status,
            "block_results": results,
            "block_count": len(results),
            "unexecuted_route_count": len(unexecuted_routes),
        }
