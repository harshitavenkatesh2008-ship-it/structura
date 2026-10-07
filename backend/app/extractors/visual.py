from typing import Any, Dict, List, Optional


class VisualExtractor:
    """
    Extractor interface for visual document regions.

    VisualExtractor v0.1 establishes a standard output format
    for figures and charts before specialized vision models
    are connected.
    """

    SUPPORTED_TYPES = {"figure", "chart"}

    def build_visual_block(
        self,
        block_type: str,
        page: int,
        bbox: List[float],
        content: Dict[str, Any],
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:

        if block_type not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported visual block type: {block_type}"
            )

        block = {
            "type": block_type,
            "page": page,
            "bbox": bbox,
            "content": content,
        }

        if confidence is not None:
            block["confidence"] = confidence

        return block