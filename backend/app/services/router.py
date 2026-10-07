"""SAFE: Structura Adaptive Fidelity-aware Extraction router.

SAFE chooses an extractor route for a single region/block. It is:

- Region-level: one decision per region, never per document.
- Deterministic: the same evidence always yields the same decision.
- Explainable: every decision carries a reason code, a plain-text reason,
  the observed signals, and the evidence that was missing or conflicting.
- Evidence-based: routing uses only caller-supplied boolean/categorical
  evidence. Raw measurements (density, column counts, ...) are carried as
  telemetry and never change the route. There are no numeric thresholds
  and no confidence values.
- Independent of extractor implementations: it only returns one of the
  standardized extractor identifiers from docs/document_graph.md.

SAFE does not evaluate extraction quality and does not escalate. Prior
risk/difficulty is recorded as a signal only. FidelityGuard (downstream)
evaluates the extraction; the integration layer owns any escalation.

Route precedence (most structurally specific first):

    table                              -> table_engine
    equation/math                      -> math_engine
    chart/figure/image                 -> vision_engine
    scanned/image-only or
    insufficient native text           -> ocr
    clean native text, low complexity  -> native_pdf

Regions the precedence cannot resolve use a deterministic, explicitly
marked fallback: native_pdf when usable native text is available,
otherwise ocr.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------
# Identifiers from docs/document_graph.md (Document Graph v1.0)
# ---------------------------------------------------------------------------

NATIVE_PDF = "native_pdf"
OCR = "ocr"
TABLE_ENGINE = "table_engine"
VISION_ENGINE = "vision_engine"
MATH_ENGINE = "math_engine"

ROUTES: Tuple[str, ...] = (NATIVE_PDF, OCR, TABLE_ENGINE, VISION_ENGINE, MATH_ENGINE)

# Precedence order, most structurally specific first.
ROUTE_PRECEDENCE: Tuple[str, ...] = (TABLE_ENGINE, MATH_ENGINE, VISION_ENGINE, OCR, NATIVE_PDF)

SUPPORTED_BLOCK_TYPES: Tuple[str, ...] = (
    "heading",
    "paragraph",
    "list",
    "table",
    "figure",
    "chart",
    "equation",
    "image",
)

RISK_LEVELS: Tuple[str, ...] = ("low", "medium", "high")

# Block types that count as specialised evidence on their own.
_TABLE_TYPES = frozenset({"table"})
_MATH_TYPES = frozenset({"equation"})
_VISION_TYPES = frozenset({"chart", "figure", "image"})

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

REASON_TABLE = "TABLE_DETECTED"
REASON_EQUATION = "EQUATION_DETECTED"
REASON_CHART_OR_FIGURE = "CHART_OR_FIGURE_DETECTED"
REASON_SCANNED_OR_INSUFFICIENT_TEXT = "SCANNED_OR_INSUFFICIENT_NATIVE_TEXT"
REASON_CLEAN_NATIVE_TEXT = "CLEAN_NATIVE_TEXT_LOW_COMPLEXITY"
REASON_FALLBACK_NATIVE_TEXT = "FALLBACK_NATIVE_TEXT"
REASON_FALLBACK_OCR = "FALLBACK_OCR"

_BOOL_FIELDS: Tuple[str, ...] = (
    "native_text_available",
    "insufficient_native_text",
    "scanned_or_image_only",
    "low_complexity",
    "text_heavy",
    "table_detected",
    "chart_or_figure_detected",
    "equation_detected",
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegionEvidence:
    """Caller-supplied evidence for one region.

    Every boolean is tri-state: True, False, or None (not provided).
    None is never treated as False.
    """

    region_id: Optional[str] = None
    page: Optional[int] = None
    bbox: Optional[Tuple[float, ...]] = None
    block_type: Optional[str] = None

    native_text_available: Optional[bool] = None
    insufficient_native_text: Optional[bool] = None
    scanned_or_image_only: Optional[bool] = None
    low_complexity: Optional[bool] = None
    text_heavy: Optional[bool] = None
    table_detected: Optional[bool] = None
    chart_or_figure_detected: Optional[bool] = None
    equation_detected: Optional[bool] = None

    # Recorded only; never changes the route.
    prior_risk_level: Optional[str] = None
    prior_risk_signals: Tuple[str, ...] = ()

    # Raw measurements (e.g. text density, column count). Telemetry only.
    raw_signals: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in _BOOL_FIELDS:
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{name} must be True, False or None, got {value!r}")
        if self.block_type is not None and self.block_type not in SUPPORTED_BLOCK_TYPES:
            raise ValueError(
                f"Unsupported block_type {self.block_type!r}; "
                f"expected one of {SUPPORTED_BLOCK_TYPES}"
            )
        if self.prior_risk_level is not None and self.prior_risk_level not in RISK_LEVELS:
            raise ValueError(
                f"Unsupported prior_risk_level {self.prior_risk_level!r}; "
                f"expected one of {RISK_LEVELS}"
            )
        # Store immutable copies so the caller's objects are never shared or mutated.
        if self.bbox is not None:
            object.__setattr__(self, "bbox", tuple(self.bbox))
        object.__setattr__(self, "prior_risk_signals", tuple(self.prior_risk_signals))
        object.__setattr__(self, "raw_signals", dict(self.raw_signals))


@dataclass(frozen=True)
class RouteDecision:
    """SAFE's routing decision for one region. Contains no confidence value."""

    route: str
    reason_code: str
    reason: str
    is_fallback: bool
    signals: Tuple[str, ...]
    complexity: Dict[str, Any]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "is_fallback": self.is_fallback,
            "signals": list(self.signals),
            "complexity": dict(self.complexity),
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _usable_native_text(ev: RegionEvidence) -> bool:
    return (
        ev.native_text_available is True
        and ev.insufficient_native_text is not True
        and ev.scanned_or_image_only is not True
    )


def _observed_signals(ev: RegionEvidence) -> Tuple[str, ...]:
    signals = []
    if ev.block_type is not None:
        signals.append(f"block_type:{ev.block_type}")
    for name in _BOOL_FIELDS:
        value = getattr(ev, name)
        if value is not None:
            signals.append(f"{name}:{str(value).lower()}")
    if ev.prior_risk_level is not None:
        signals.append(f"prior_risk_level:{ev.prior_risk_level}")
    for sig in ev.prior_risk_signals:
        signals.append(f"prior_risk_signal:{sig}")
    return tuple(sorted(signals))


def _missing_evidence(ev: RegionEvidence) -> Tuple[str, ...]:
    missing = [name for name in _BOOL_FIELDS if getattr(ev, name) is None]
    if ev.block_type is None:
        missing.append("block_type")
    return tuple(sorted(missing))


def _conflicting_evidence(ev: RegionEvidence) -> Tuple[str, ...]:
    conflicts = []
    if ev.block_type in _TABLE_TYPES and ev.table_detected is False:
        conflicts.append("block_type:table vs table_detected:false")
    if ev.block_type in _MATH_TYPES and ev.equation_detected is False:
        conflicts.append("block_type:equation vs equation_detected:false")
    if ev.block_type in _VISION_TYPES and ev.chart_or_figure_detected is False:
        conflicts.append(f"block_type:{ev.block_type} vs chart_or_figure_detected:false")
    if ev.native_text_available is True and ev.insufficient_native_text is True:
        conflicts.append("native_text_available:true vs insufficient_native_text:true")
    if ev.native_text_available is False and ev.insufficient_native_text is False:
        conflicts.append("native_text_available:false vs insufficient_native_text:false")
    return tuple(conflicts)


def _candidates(ev: RegionEvidence) -> Tuple[Tuple[str, str], ...]:
    """Every route whose rule fired, as (route, reason_code), in precedence order."""
    fired = {}
    if ev.table_detected is True or ev.block_type in _TABLE_TYPES:
        fired[TABLE_ENGINE] = REASON_TABLE
    if ev.equation_detected is True or ev.block_type in _MATH_TYPES:
        fired[MATH_ENGINE] = REASON_EQUATION
    if ev.chart_or_figure_detected is True or ev.block_type in _VISION_TYPES:
        fired[VISION_ENGINE] = REASON_CHART_OR_FIGURE
    if ev.scanned_or_image_only is True or ev.insufficient_native_text is True:
        fired[OCR] = REASON_SCANNED_OR_INSUFFICIENT_TEXT
    if _usable_native_text(ev) and ev.low_complexity is True:
        fired[NATIVE_PDF] = REASON_CLEAN_NATIVE_TEXT
    return tuple((route, fired[route]) for route in ROUTE_PRECEDENCE if route in fired)


_REASON_TEXT = {
    REASON_TABLE: "Table evidence present; table_engine takes precedence over other routes.",
    REASON_EQUATION: "Equation/math evidence present and no table evidence.",
    REASON_CHART_OR_FIGURE: "Chart/figure/image evidence present and no table or equation evidence.",
    REASON_SCANNED_OR_INSUFFICIENT_TEXT: (
        "Scanned/image-only or insufficient native text, and no table, equation "
        "or chart/figure evidence."
    ),
    REASON_CLEAN_NATIVE_TEXT: "Usable native text with low complexity and no specialised evidence.",
}


def _fallback(ev: RegionEvidence) -> Tuple[str, str, str]:
    """Deterministic fallback for regions the precedence rules cannot resolve."""
    if _usable_native_text(ev):
        if ev.low_complexity is False:
            why = "layout is not low-complexity"
        else:
            why = "layout complexity was not provided"
        return (
            NATIVE_PDF,
            REASON_FALLBACK_NATIVE_TEXT,
            "Fallback: no specialised evidence and "
            f"{why}; native text is usable, so native_pdf is used. "
            "This is a fallback, not a high-confidence route.",
        )
    if ev.native_text_available is False:
        why = "native text is not available"
    else:
        why = "native text availability was not established"
    return (
        OCR,
        REASON_FALLBACK_OCR,
        f"Fallback: no specialised evidence and {why}, so ocr is used. "
        "This is a fallback, not a high-confidence route.",
    )


def route_region(evidence: RegionEvidence) -> RouteDecision:
    """Choose an extractor route for one region. Pure and deterministic."""
    if not isinstance(evidence, RegionEvidence):
        raise TypeError("route_region expects a RegionEvidence instance")

    candidates = _candidates(evidence)
    if candidates:
        route, reason_code = candidates[0]
        reason = _REASON_TEXT[reason_code]
        is_fallback = False
        matched_rule = reason_code
    else:
        route, reason_code, reason = _fallback(evidence)
        is_fallback = True
        matched_rule = "fallback"

    complexity = {
        "low_complexity": evidence.low_complexity,
        "text_heavy": evidence.text_heavy,
        "raw_signals": dict(evidence.raw_signals),
    }
    metadata = {
        "region_id": evidence.region_id,
        "page": evidence.page,
        "bbox": list(evidence.bbox) if evidence.bbox is not None else None,
        "matched_rule": matched_rule,
        "candidate_routes": [r for r, _ in candidates],
        "outranked_routes": [r for r, _ in candidates[1:]],
        "missing_evidence": list(_missing_evidence(evidence)),
        "conflicting_evidence": list(_conflicting_evidence(evidence)),
        "prior_risk": {
            "level": evidence.prior_risk_level,
            "signals": list(evidence.prior_risk_signals),
        },
        "raw_signals": dict(evidence.raw_signals),
    }
    return RouteDecision(
        route=route,
        reason_code=reason_code,
        reason=reason,
        is_fallback=is_fallback,
        signals=_observed_signals(evidence),
        complexity=complexity,
        metadata=metadata,
    )


def evidence_from_block(block: Mapping[str, Any], **evidence: Any) -> RegionEvidence:
    """Build RegionEvidence from a Document Graph block without modifying it.

    Reads only ``id``, ``page``, ``bbox``, ``type`` and ``risk``. Additional
    caller-supplied evidence (e.g. ``scanned_or_image_only=True``) can be
    passed as keyword arguments.
    """
    risk = block.get("risk") or {}
    return RegionEvidence(
        region_id=block.get("id"),
        page=block.get("page"),
        bbox=tuple(block["bbox"]) if block.get("bbox") is not None else None,
        block_type=block.get("type"),
        prior_risk_level=risk.get("level"),
        prior_risk_signals=tuple(risk.get("signals") or ()),
        **evidence,
    )
