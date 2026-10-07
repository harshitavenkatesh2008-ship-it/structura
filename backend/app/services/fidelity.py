from typing import Any, Dict, List


VISUAL_ISSUES = {
    "missing_visual_content",
    "missing_chart_title",
    "missing_chart_description",
    "missing_figure_description",
}

EQUATION_ISSUES = {
    "missing_equation_content",
    "missing_latex",
    "missing_equation_raw_text",
}

PROVENANCE_ISSUES = {
    "missing_page",
    "invalid_page",
    "invalid_bbox",
    "invalid_bbox_coordinates",
    "invalid_bbox_geometry",
}

CONFIDENCE_ISSUES = {
    "low_extractor_confidence",
    "very_low_extractor_confidence",
    "invalid_extractor_confidence",
}


def determine_escalation(
    block: Dict[str, Any],
    fidelity_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert FidelityGuard output into an explicit SAFE routing decision.

    This function does not execute another extractor.
    It tells the pipeline what should happen next.
    """

    action = fidelity_result.get("action", "escalate")
    issues: List[str] = fidelity_result.get("issues", [])

    block_type = block.get("type")

    # Trusted extraction: no retry required.
    if action == "accept":
        return {
            "decision": "accept",
            "retry_required": False,
            "strategy": "none",
            "target": block_type,
            "reason": "fidelity_checks_passed",
        }

    issue_set = set(issues)

    # Visual regions should be retried by visual intelligence.
    if issue_set.intersection(VISUAL_ISSUES):
        strategy = "visual_reextract"

    # Equations should be retried by equation intelligence.
    elif issue_set.intersection(EQUATION_ISSUES):
        strategy = "equation_reextract"

    # Broken provenance requires region/page reconstruction.
    elif issue_set.intersection(PROVENANCE_ISSUES):
        strategy = "provenance_reconstruct"

    # Low-confidence output should be retried with a stronger extractor.
    elif issue_set.intersection(CONFIDENCE_ISSUES):
        strategy = "stronger_extractor"

    # Unknown high-risk failure: use specialist fallback.
    else:
        strategy = "specialist_fallback"

    return {
        "decision": action,
        "retry_required": True,
        "strategy": strategy,
        "target": block_type,
        "reason": issues,
    }