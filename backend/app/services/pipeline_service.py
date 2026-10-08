
"""C11 integration: extraction, Document Graph, routing, and fidelity."""

from pathlib import Path
from typing import Any

from backend.app.extractors.base import NativePDFExtractor
from backend.app.extractors.registry import ExtractorRegistry, build_default_registry
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

        # 2. Convert the result into the canonical C7 Document Graph.
        document: Document = to_document_graph(extracted)

        results: list[dict[str, Any]] = []

        # 3. Run SAFE Router and FidelityGuard for each block.
        for page in document.pages:
            for block in page.blocks:
                block_data = block.model_dump(mode="json")

                # SAFE Router recommends the appropriate extractor.
                evidence = evidence_from_block(block_data)
                route = route_region(evidence)

                # FidelityGuard evaluates the current extraction.
                fidelity = calculate_fidelity(block_data)

                # FidelityGuard recommends any follow-up action.
                escalation = determine_escalation(
                    block_data,
                    fidelity,
                )

                # Specialist extraction has not been implemented yet.
                route_executed = False

                # A matching route is already satisfied by the
                # initial extraction; other routes need a specialist.
                requires_specialist = (
                    route.route != block.extractor
                )

                resolved = self.registry.resolve_status(
                    route.route,
                    block.extractor,
                )
                route_status = (
                    "unsupported"
                    if resolved == "unsupported"
                    else ("already_satisfied" if resolved == "already_satisfied" else resolved)
                )

                results.append(
                    {
                        "block_id": block.id,
                        "page": block.page,
                        "initial_extractor": block.extractor,
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

        # 4. Determine the aggregate pipeline status.
        #
        # Fidelity acceptance alone does not mean that the SAFE
        # Router's recommended extraction was performed.

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

