import math
from typing import Any, Dict


def calculate_fidelity(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate the reliability of an extracted document block.

    FidelityGuard checks:
    - content integrity
    - page provenance
    - bounding-box provenance and geometry
    - block type
    - extractor confidence
    - visual extraction issues
    - equation extraction issues
    """

    score = 1.0
    issues = []

    # 1. Content check
    content = block.get("content")

    if content is None or content == "" or content == {}:
        score -= 0.35
        issues.append("missing_content")

    # 2. Page provenance check
    page = block.get("page")

    if page is None:
        score -= 0.20
        issues.append("missing_page")

    elif isinstance(page, bool) or not isinstance(page, int) or page < 1:
        score -= 0.20
        issues.append("invalid_page")

    # 3. Bounding-box provenance and geometry check
    bbox = block.get("bbox")

    if not isinstance(bbox, list) or len(bbox) != 4:
        score -= 0.25
        issues.append("invalid_bbox")

    else:
        valid_coordinates = True

        for coordinate in bbox:
            if isinstance(coordinate, bool) or not isinstance(
                coordinate, (int, float)
            ):
                valid_coordinates = False
                break

            if not math.isfinite(coordinate):
                valid_coordinates = False
                break

        if not valid_coordinates:
            score -= 0.25
            issues.append("invalid_bbox_coordinates")

        else:
            x1, y1, x2, y2 = bbox

            if x2 <= x1 or y2 <= y1:
                score -= 0.25
                issues.append("invalid_bbox_geometry")

    # 4. Block type check
    block_type = block.get("type")

    valid_types = {
        "heading",
        "paragraph",
        "list",
        "table",
        "figure",
        "chart",
        "equation",
    }

    if block_type not in valid_types:
        score -= 0.20
        issues.append("unknown_block_type")

    # 5. Extractor confidence check
    extractor_confidence = block.get("confidence")

    if extractor_confidence is not None:
        try:
            if isinstance(extractor_confidence, bool):
                raise ValueError

            extractor_confidence = float(extractor_confidence)

            if not math.isfinite(extractor_confidence):
                score -= 0.25
                issues.append("invalid_extractor_confidence")

            elif extractor_confidence < 0.0 or extractor_confidence > 1.0:
                score -= 0.25
                issues.append("invalid_extractor_confidence")

            elif extractor_confidence < 0.50:
                score -= 0.30
                issues.append("very_low_extractor_confidence")

            elif extractor_confidence < 0.75:
                score -= 0.15
                issues.append("low_extractor_confidence")

        except (TypeError, ValueError):
            score -= 0.25
            issues.append("invalid_extractor_confidence")

    # 6. Visual Intelligence validation
    visual_issues = block.get("visual_issues", [])

    if isinstance(visual_issues, list):
        for visual_issue in visual_issues:
            if visual_issue not in issues:
                issues.append(visual_issue)

        if "missing_visual_content" in visual_issues:
            score -= 0.35

        if "missing_chart_title" in visual_issues:
            score -= 0.10

        if "missing_chart_description" in visual_issues:
            score -= 0.20

        if "missing_figure_description" in visual_issues:
            score -= 0.20

    # 7. Equation Intelligence validation
    equation_issues = block.get("equation_issues", [])

    if isinstance(equation_issues, list):
        for equation_issue in equation_issues:
            if equation_issue not in issues:
                issues.append(equation_issue)

        if "missing_equation_content" in equation_issues:
            score -= 0.35

        if "missing_latex" in equation_issues:
            score -= 0.20

        if "missing_equation_raw_text" in equation_issues:
            score -= 0.15

    # Keep score between 0 and 1
    score = max(0.0, min(1.0, score))

    # Convert score into explainable risk
    if score >= 0.85:
        risk = "low"
    elif score >= 0.60:
        risk = "medium"
    else:
        risk = "high"

    # Issues that must never be silently accepted
    review_required_issues = {
        "low_extractor_confidence",
        "very_low_extractor_confidence",
        "invalid_extractor_confidence",
        "invalid_page",
        "invalid_bbox",
        "invalid_bbox_coordinates",
        "invalid_bbox_geometry",
        "missing_visual_content",
        "missing_chart_title",
        "missing_chart_description",
        "missing_figure_description",
        "missing_equation_content",
        "missing_latex",
        "missing_equation_raw_text",
    }

    if review_required_issues.intersection(issues) and risk == "low":
        risk = "medium"

    # Decide what the pipeline should do next
    if risk == "low":
        action = "accept"
    elif risk == "medium":
        action = "review"
    else:
        action = "escalate"

    return {
        "fidelity_score": round(score, 2),
        "risk": risk,
        "action": action,
        "flagged": risk == "high",
        "issues": issues,
    }