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

    # 5. Extractor confidence check
    extractor_confidence = block.get("confidence")

    if extractor_confidence is not None:
        try:
            extractor_confidence = float(extractor_confidence)

            if extractor_confidence < 0.0 or extractor_confidence > 1.0:
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

    # Keep score between 0 and 1
    score = max(0.0, min(1.0, score))

    # Convert score into explainable risk
    if score >= 0.85:
        risk = "low"
    elif score >= 0.60:
        risk = "medium"
    else:
        risk = "high"

    # Confidence concerns must never be silently accepted
    confidence_issues = {
        "low_extractor_confidence",
        "very_low_extractor_confidence",
        "invalid_extractor_confidence",
    }

    if confidence_issues.intersection(issues) and risk == "low":
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