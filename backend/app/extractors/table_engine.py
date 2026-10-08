"""
Structura Table Engine (P4 Stage 1 & Stage 2).
Implements universal Document Graph v1.0 table block extraction and cross-page stitching.

Rules:
- Never silently modify or autocorrect extracted text or numbers.
- Ensure strict bounding box validation ([x0, y0, x1, y1] in [0.0, 1.0]).
- Standardized extractor identifier: "table_engine".
- Produce fully traceable Document Graph blocks.
- Stitch continuation tables while preserving anchor identity and original cell text verbatim.
"""

import copy
import uuid
from typing import Any, Dict, List, Optional, Sequence, Union

try:
    from backend.app.validators.financial import validate_table_financials
except ImportError:
    try:
        from app.validators.financial import validate_table_financials
    except ImportError:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from backend.app.validators.financial import validate_table_financials


def validate_bounding_box(bbox: Sequence[Union[int, float]]) -> List[float]:
    """
    Validate normalized bounding box according to Document Graph v1.0 standard:
    - Must contain exactly 4 values: [x0, y0, x1, y1].
    - Every coordinate must be between 0.0 and 1.0.
    - Top-left coordinate convention: x0 <= x1 and y0 <= y1.

    Raises:
        ValueError: If any validation rule is violated.
    Returns:
        List of 4 floats: [x0, y0, x1, y1].
    """
    if not isinstance(bbox, (list, tuple)):
        raise ValueError(f"Bounding box must be a list or tuple, got {type(bbox).__name__}")

    if len(bbox) != 4:
        raise ValueError(f"Bounding box must contain exactly 4 values [x0, y0, x1, y1], got {len(bbox)}")

    converted_bbox: List[float] = []
    for idx, coord in enumerate(bbox):
        if not isinstance(coord, (int, float)):
            raise ValueError(f"Bounding box coordinate at index {idx} must be a number, got {type(coord).__name__}")
        float_coord = float(coord)
        if not (0.0 <= float_coord <= 1.0):
            raise ValueError(
                f"Bounding box coordinate at index {idx} ({float_coord}) is out of bounds; all values must be between 0.0 and 1.0"
            )
        converted_bbox.append(float_coord)

    x0, y0, x1, y1 = converted_bbox
    if x0 > x1:
        raise ValueError(f"Invalid bounding box: x0 ({x0}) cannot be greater than x1 ({x1})")
    if y0 > y1:
        raise ValueError(f"Invalid bounding box: y0 ({y0}) cannot be greater than y1 ({y1})")

    return converted_bbox


def are_tables_stitch_compatible(
    table1: Dict[str, Any],
    table2: Dict[str, Any]
) -> bool:
    """
    Detect whether two table blocks are continuations of the same table using
    deterministic structural evidence:
    - Both blocks are of type 'table'.
    - Consecutive or near-consecutive pages (page2 immediately follows table1's last page).
    - Compatible column counts.
    - Compatible headers (matching headers, or continuation page without headers).
    """
    if not (isinstance(table1, dict) and isinstance(table2, dict)):
        return False

    if table1.get("type") != "table" or table2.get("type") != "table":
        return False

    # Check page consecutiveness
    last_page1 = table1.get("_last_page", table1.get("page"))
    page2 = table2.get("page")
    if not (isinstance(last_page1, int) and isinstance(page2, int)):
        return False

    if page2 != last_page1 + 1:
        return False

    content1 = table1.get("content", {})
    content2 = table2.get("content", {})
    headers1 = content1.get("headers", [])
    headers2 = content2.get("headers", [])
    rows1 = content1.get("rows", [])
    rows2 = content2.get("rows", [])

    # Determine column counts
    col_count1 = len(headers1) if headers1 else (len(rows1[0]) if rows1 else 0)
    col_count2 = len(headers2) if headers2 else (len(rows2[0]) if rows2 else 0)

    if col_count1 == 0 or col_count2 == 0 or col_count1 != col_count2:
        return False

    # Check header compatibility
    if headers1 and headers2:
        norm_h1 = [str(h).strip().lower() for h in headers1]
        norm_h2 = [str(h).strip().lower() for h in headers2]
        if norm_h1 != norm_h2:
            return False
    elif not headers1 and headers2:
        # First table had no headers, cannot confirm compatibility
        return False

    return True


def stitch_two_tables(
    table1: Dict[str, Any],
    table2: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stitch two compatible table blocks into a single Document Graph table block.

    Rules:
    - Preserves table1's identity, page, bbox, and reading_order as the anchor.
    - Combines rows in sequential reading order.
    - Prevents duplicating repeated continuation headers.
    - Preserves all original cell text verbatim without mutation or recalculation.
    - Preserves traceability by recording table2's ID in children.
    - Sets extractor = 'table_engine'.
    """
    content1 = table1.get("content", {})
    content2 = table2.get("content", {})
    headers1 = list(content1.get("headers", []))
    headers2 = list(content2.get("headers", []))
    rows1 = [list(r) for r in content1.get("rows", [])]
    rows2 = [list(r) for r in content2.get("rows", [])]

    # Combine rows in reading order
    combined_rows: List[List[str]] = [list(r) for r in rows1]

    # Detect if table2's data rows start with a repeated header row
    norm_headers1 = [str(h).strip().lower() for h in headers1] if headers1 else []
    skip_first_row = False
    if rows2 and norm_headers1:
        first_row_norm = [str(c).strip().lower() for c in rows2[0]]
        if first_row_norm == norm_headers1:
            skip_first_row = True

    for idx, row in enumerate(rows2):
        if idx == 0 and skip_first_row:
            continue
        # Preserve original cell values exactly
        combined_rows.append([str(c) for c in row])

    # Preserve and extend children for complete traceability
    combined_children = list(table1.get("children", []))
    table2_id = table2.get("id")
    if table2_id and table2_id not in combined_children:
        combined_children.append(table2_id)
    for child in table2.get("children", []):
        if child not in combined_children:
            combined_children.append(child)

    # Re-evaluate financial/numeric validation on the combined rows
    validation_result = validate_table_financials(headers1, combined_rows)

    combined_signals = list(validation_result.get("signals", []))
    if "stitched_cross_page" not in combined_signals:
        combined_signals.append("stitched_cross_page")

    # Combine flags while preserving unique values
    combined_flags = list(dict.fromkeys(
        table1.get("flags", []) + table2.get("flags", []) + validation_result.get("flags", [])
    ))

    # Determine last page for multi-page chains
    last_page2 = table2.get("_last_page", table2.get("page", table1["page"]))

    stitched_block: Dict[str, Any] = {
        "id": table1["id"],
        "type": "table",
        "page": table1["page"],
        "bbox": list(table1["bbox"]),
        "reading_order": table1["reading_order"],
        "content": {
            "headers": headers1,
            "rows": combined_rows,
        },
        "extractor": "table_engine",
        "risk": {
            "score": validation_result["score"],
            "level": validation_result["level"],
            "signals": combined_signals,
        },
        "confidence": table1.get("confidence"),
        "flags": combined_flags,
        "traceable": True,
        "parent": table1.get("parent"),
        "children": combined_children,
        "_last_page": last_page2,
    }

    return stitched_block


def stitch_tables(
    tables: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Accepts table blocks from consecutive pages and stitches compatible
    continuation tables in document reading order.

    Incompatible tables are kept separate and unmodified.
    """
    if not tables:
        return []

    # Sort tables by page and reading_order to process in logical document sequence
    sorted_tables = [
        copy.deepcopy(t) for t in sorted(
            tables,
            key=lambda t: (t.get("page", 0), t.get("reading_order", 0))
        )
    ]

    stitched_list: List[Dict[str, Any]] = []
    current = sorted_tables[0]

    for next_table in sorted_tables[1:]:
        if are_tables_stitch_compatible(current, next_table):
            current = stitch_two_tables(current, next_table)
        else:
            # Clean internal helper key if present before saving
            current.pop("_last_page", None)
            stitched_list.append(current)
            current = next_table

    current.pop("_last_page", None)
    stitched_list.append(current)

    return stitched_list


class TableEngine:
    """
    Table extraction engine component (P4).
    Processes structured table data into compliant Document Graph v1.0 blocks
    and stitches cross-page tables.
    """

    EXTRACTOR_NAME = "table_engine"

    def __init__(self) -> None:
        pass

    def extract(
        self,
        headers: List[str],
        rows: List[List[str]],
        page: int,
        bbox: Sequence[Union[int, float]],
        reading_order: int,
        block_id: Optional[str] = None,
        confidence: Optional[float] = None,
        parent: Optional[str] = None,
        children: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract and assemble a Document Graph v1.0 table block.

        Preserves all raw text in headers and rows without silent correction.
        Validates bbox and performs financial/numeric consistency checks.
        """
        if not isinstance(page, int) or page < 1:
            raise ValueError(f"Page must be a 1-based positive integer, got {page}")

        validated_bbox = validate_bounding_box(bbox)

        # Preserve cell text verbatim (deep copy list structures without modifying string contents)
        preserved_headers = [str(h) for h in headers]
        preserved_rows = [[str(cell) for cell in row] for row in rows]

        # Financial & numeric consistency validation
        validation_result = validate_table_financials(preserved_headers, preserved_rows)

        block_identifier = block_id if block_id is not None else f"block_{uuid.uuid4().hex[:6]}"

        return {
            "id": block_identifier,
            "type": "table",
            "page": page,
            "bbox": validated_bbox,
            "reading_order": reading_order,
            "content": {
                "headers": preserved_headers,
                "rows": preserved_rows,
            },
            "extractor": self.EXTRACTOR_NAME,
            "risk": {
                "score": validation_result["score"],
                "level": validation_result["level"],
                "signals": validation_result["signals"],
            },
            "confidence": confidence,
            "flags": validation_result["flags"],
            "traceable": True,
            "parent": parent,
            "children": children if children is not None else [],
        }

    def stitch(
        self,
        table1: Dict[str, Any],
        table2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Stitch two compatible tables."""
        return stitch_two_tables(table1, table2)

    def stitch_tables(
        self,
        tables: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Stitch a sequence of tables across pages."""
        return stitch_tables(tables)


def extract_table(
    headers: List[str],
    rows: List[List[str]],
    page: int,
    bbox: Sequence[Union[int, float]],
    reading_order: int,
    block_id: Optional[str] = None,
    confidence: Optional[float] = None,
    parent: Optional[str] = None,
    children: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to extract a Document Graph v1 table block using TableEngine.
    """
    engine = TableEngine()
    return engine.extract(
        headers=headers,
        rows=rows,
        page=page,
        bbox=bbox,
        reading_order=reading_order,
        block_id=block_id,
        confidence=confidence,
        parent=parent,
        children=children,
    )
