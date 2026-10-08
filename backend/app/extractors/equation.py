from typing import Any, Dict, List, Optional


class EquationExtractor:
    """
    Equation Intelligence component for Structura.

    Builds standardized equation blocks and performs
    structural validation before FidelityGuard analysis.
    """

    @staticmethod
    def validate_equation_content(
        content: Dict[str, Any],
    ) -> List[str]:
        """
        Validate structured equation extraction output.

        Expected equation content may contain:
        - latex: normalized LaTeX representation
        - raw_text: original extracted equation text
        """

        issues: List[str] = []

        if not isinstance(content, dict) or not content:
            issues.append("missing_equation_content")
            return issues

        latex = content.get("latex")
        raw_text = content.get("raw_text")

        if not latex:
            issues.append("missing_latex")

        if not raw_text:
            issues.append("missing_equation_raw_text")

        return issues

    def build_equation_block(
        self,
        page: int,
        bbox: List[float],
        content: Dict[str, Any],
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Build a standardized equation block for Structura.
        """

        equation_issues = self.validate_equation_content(content)

        block: Dict[str, Any] = {
            "type": "equation",
            "page": page,
            "bbox": bbox,
            "content": content,
            "equation_issues": equation_issues,
        }

        if confidence is not None:
            block["confidence"] = confidence

        return block