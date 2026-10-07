from typing import Any, Dict


def calculate_fidelity(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate the reliability of an extracted document block.

    This is FidelityGuard v0.1.
    It performs basic structural and provenance validation.
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

    # 3. Bounding-box provenance check
    bbox = block.get("bbox")

    if not bbox or not isinstance(bbox, list) or len(bbox) != 4:
        score -= 0.25
        issues.append("invalid_bbox")

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

    # Keep score between 0 and 1
    score = max(0.0, min(1.0, score))

    # Convert score into explainable risk
    if score >= 0.85:
        risk = "low"
    elif score >= 0.60:
        risk = "medium"
    else:
        risk = "high"

    return {
        "fidelity_score": round(score, 2),
        "risk": risk,
        "flagged": risk == "high",
        "issues": issues,
    }