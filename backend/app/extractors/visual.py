from typing import Any, Dict, List, Optional


class VisualExtractor:
    """
    Visual Intelligence component for Structura.

    Handles structured representation and validation
    of chart and figure regions before they are passed
    to FidelityGuard.
    """

    SUPPORTED_TYPES = {"figure", "chart"}

    @staticmethod
    def validate_visual_content(
        block_type: str,
        content: Dict[str, Any],
    ) -> List[str]:
        """
        Validate extracted chart or figure content.

        Returns visual-specific issues.
        An empty list means no obvious structural
        problem was detected.
        """

        issues: List[str] = []

        if not isinstance(content, dict) or not content:
            issues.append("missing_visual_content")
            return issues

        if block_type == "chart":
            if not content.get("title"):
                issues.append("missing_chart_title")

            if not content.get("description"):
                issues.append("missing_chart_description")

        elif block_type == "figure":
            if not content.get("description"):
                issues.append("missing_figure_description")

        return issues

    def build_visual_block(
        self,
        block_type: str,
        page: int,
        bbox: List[float],
        content: Dict[str, Any],
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Build a standardized visual block that can be
        consumed by Structura's FidelityGuard.
        """

        if block_type not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported visual block type: {block_type}"
            )

        visual_issues = self.validate_visual_content(
            block_type,
            content,
        )

        block: Dict[str, Any] = {
            "type": block_type,
            "page": page,
            "bbox": bbox,
            "content": content,
            "visual_issues": visual_issues,
        }

        if confidence is not None:
            block["confidence"] = confidence

        return block