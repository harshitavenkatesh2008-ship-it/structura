"""
Financial and numeric consistency validators for extracted tables (P4 Stage 3).
Complies with Structura Document Graph v1.0 rules:
- Never silently modify, normalize, or recalculate raw extracted text.
- Accurately detect clear financial totals and component values.
- Avoid false positives when a row is not clearly a summary total.
- Record inconsistencies in risk signals and flags (e.g. NUMERIC_INCONSISTENCY).
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple


def parse_numeric_cell(raw_val: Any) -> Optional[float]:
    """
    Parse a numeric table cell value into a float.
    Handles currency symbols, metric suffixes (K, M, B, T), percentages,
    accounting negatives e.g. (100), comma separators, and financial nil dashes.

    Returns None if the value cannot be parsed into a numeric scalar.
    Original string is NEVER modified.
    """
    if raw_val is None:
        return None

    val_str = str(raw_val).strip()
    if not val_str:
        return None

    # Common financial notation for zero / nil balances (single dash or en/em dash)
    if val_str in ("-", "–", "—", "nil", "None"):
        return 0.0

    # Check for accounting negative (e.g., "(100)" or "($100M)")
    is_negative = False
    if val_str.startswith("(") and val_str.endswith(")"):
        is_negative = True
        val_str = val_str[1:-1].strip()
    elif val_str.startswith("-"):
        is_negative = True
        val_str = val_str[1:].strip()

    # Remove currency symbols and formatting characters
    # e.g., $, €, £, ¥, ₹
    val_str = re.sub(r"[\$€£¥₹\s]", "", val_str)

    multiplier = 1.0
    if val_str:
        last_char = val_str[-1].upper()
        if last_char == "K":
            multiplier = 1e3
            val_str = val_str[:-1]
        elif last_char == "M":
            multiplier = 1e6
            val_str = val_str[:-1]
        elif last_char == "B":
            multiplier = 1e9
            val_str = val_str[:-1]
        elif last_char == "T":
            multiplier = 1e12
            val_str = val_str[:-1]
        elif last_char == "%":
            multiplier = 0.01
            val_str = val_str[:-1]

    # Remove comma thousand separators in numbers like "1,000,000"
    val_str = val_str.replace(",", "")

    try:
        parsed = float(val_str)
        result = parsed * multiplier
        return -result if is_negative else result
    except ValueError:
        return None


def is_total_row_label(label: str) -> bool:
    """
    Deterministically check whether a row label clearly denotes a financial total.
    Uses strict whole-word boundary matching and exclusions to prevent false positives
    (such as 'network', 'consumer', 'summary', or '% of total').
    """
    if not label:
        return False

    cleaned = label.strip().lower()

    # Exclusions: ratios or percentages referencing totals are not total rows
    exclusion_patterns = [
        r"(%|\bpercent|\bpercentage|\bshare|\bratio)\s+(of\s+)?total\b",
        r"as\s+a\s+%\s+of\b",
        r"\bnotes?\s+to\b",
    ]
    if any(re.search(pat, cleaned) for pat in exclusion_patterns):
        return False

    # Positive matches: clear summary / total / net keywords with word boundaries
    positive_patterns = [
        r"\b(grand\s+total|subtotal|total)\b",
        r"^(sum|aggregate)\b",
        r"\b(sum|aggregate)$",
        r"\bnet\s+(income|loss|profit|total|debt|amount|revenue|margin|expenditure)\b",
        r"^net\b",
    ]

    return any(re.search(pat, cleaned) is not None for pat in positive_patterns)


def validate_table_financials(
    headers: Optional[List[str]],
    rows: List[List[str]]
) -> Dict[str, Any]:
    """
    Perform financial and numeric consistency validation across table rows.

    Detects clear total/subtotal rows and verifies whether the sum of component rows
    above the total matches the stated total.

    Returns:
        dict containing:
        - signals: list of signal strings e.g. ["numeric_consistency_pass"]
        - flags: list of flag strings e.g. ["NUMERIC_INCONSISTENCY"]
        - score: risk score (0.0 - 1.0)
        - level: risk level ("low", "medium", "high")
    """
    if not rows or len(rows) < 2:
        return {
            "signals": [],
            "flags": [],
            "score": 0.12,
            "level": "low"
        }

    signals: List[str] = []
    flags: List[str] = []
    has_total_check = False
    inconsistencies_found = 0
    checks_passed = 0

    num_cols = max(len(r) for r in rows)
    last_total_idx = -1

    for row_idx, row in enumerate(rows):
        if not row:
            continue

        label_cell = str(row[0]) if len(row) > 0 else ""
        if not is_total_row_label(label_cell):
            continue

        # Candidate total row found. Components must exist strictly above it
        start_comp_idx = last_total_idx + 1
        if row_idx <= start_comp_idx:
            continue

        # Check each subsequent column with numeric data
        row_has_valid_check = False
        for col_idx in range(1, min(len(row), num_cols)):
            total_val = parse_numeric_cell(row[col_idx])
            if total_val is None:
                continue

            # Gather component values in this column between start_comp_idx and row_idx
            component_values: List[float] = []
            all_components_valid = True

            for comp_idx in range(start_comp_idx, row_idx):
                comp_row = rows[comp_idx]
                if col_idx < len(comp_row):
                    raw_comp = comp_row[col_idx]
                    # If cell is completely empty or None, treat as non-contributing entry
                    if raw_comp is None or str(raw_comp).strip() == "":
                        continue
                    parsed_comp = parse_numeric_cell(raw_comp)
                    if parsed_comp is not None:
                        component_values.append(parsed_comp)
                    else:
                        # Non-empty cell could not be parsed numerically; incomplete component series
                        all_components_valid = False
                        break
                else:
                    all_components_valid = False
                    break

            # Need at least 2 component values to represent a meaningful summation
            if all_components_valid and len(component_values) >= 2:
                has_total_check = True
                row_has_valid_check = True
                computed_sum = sum(component_values)

                # Tolerance for floating-point and rounding differences
                tolerance = max(1e-4, abs(total_val) * 1e-4)
                if math.isclose(computed_sum, total_val, abs_tol=tolerance):
                    checks_passed += 1
                else:
                    inconsistencies_found += 1

        if row_has_valid_check:
            last_total_idx = row_idx

    if has_total_check:
        if inconsistencies_found > 0:
            signals.append("numeric_consistency_fail")
            flags.append("NUMERIC_INCONSISTENCY")
            return {
                "signals": signals,
                "flags": flags,
                "score": 0.70,
                "level": "high"
            }
        elif checks_passed > 0:
            signals.append("numeric_consistency_pass")
            return {
                "signals": signals,
                "flags": flags,
                "score": 0.12,
                "level": "low"
            }

    # Default baseline when no totals are present or non-evaluable
    return {
        "signals": signals,
        "flags": flags,
        "score": 0.12,
        "level": "low"
    }
