"""
Tests for Structura Table Engine (P4 Stage 1, Stage 2, and Stage 3).
Validates:
- Document Graph v1.0 compliance
- Strict bbox validation
- Verbatim text preservation (no silent correction)
- Financial & numeric consistency checking (Stage 1 & Stage 3 refinement)
- Cross-page table stitching with anchor preservation and header deduplication (Stage 2)
- Prevention of false positives in financial total detection (Stage 3)
"""

import pytest
from backend.app.extractors.table_engine import (
    TableEngine,
    are_tables_stitch_compatible,
    extract_table,
    stitch_tables,
    stitch_two_tables,
    validate_bounding_box,
)
from backend.app.validators.financial import (
    is_total_row_label,
    parse_numeric_cell,
    validate_table_financials,
)


# ============================================================================
# Stage 1 Tests
# ============================================================================

def test_basic_table_creation():
    """Verify basic table extraction outputs expected block structure and types."""
    headers = ["Item", "Cost"]
    rows = [["Service A", "50"], ["Service B", "75"]]
    bbox = [0.1, 0.2, 0.8, 0.6]

    block = extract_table(
        headers=headers,
        rows=rows,
        page=1,
        bbox=bbox,
        reading_order=1,
        block_id="block_001",
    )

    assert block["id"] == "block_001"
    assert block["type"] == "table"
    assert block["extractor"] == "table_engine"
    assert block["page"] == 1
    assert block["reading_order"] == 1
    assert block["traceable"] is True
    assert block["content"]["headers"] == headers
    assert block["content"]["rows"] == rows


def test_required_document_graph_fields():
    """Verify that all required Document Graph v1.0 fields are present."""
    required_top_level_keys = {
        "id",
        "type",
        "page",
        "bbox",
        "reading_order",
        "content",
        "extractor",
        "risk",
        "confidence",
        "flags",
        "traceable",
        "parent",
        "children",
    }

    engine = TableEngine()
    block = engine.extract(
        headers=["Col1", "Col2"],
        rows=[["Val1", "Val2"]],
        page=2,
        bbox=[0.05, 0.10, 0.95, 0.80],
        reading_order=3,
        parent="parent_block_01",
        children=["child_01"],
    )

    # Check top-level keys
    assert set(block.keys()) == required_top_level_keys

    # Check content schema
    assert "headers" in block["content"]
    assert "rows" in block["content"]
    assert isinstance(block["content"]["headers"], list)
    assert isinstance(block["content"]["rows"], list)

    # Check risk schema
    assert "score" in block["risk"]
    assert "level" in block["risk"]
    assert "signals" in block["risk"]
    assert block["risk"]["level"] in {"low", "medium", "high"}
    assert isinstance(block["risk"]["score"], (int, float))
    assert isinstance(block["risk"]["signals"], list)

    # Check linkage and traceability
    assert block["parent"] == "parent_block_01"
    assert block["children"] == ["child_01"]
    assert block["traceable"] is True


def test_bbox_validation():
    """Verify strict bounding box validation rules."""
    # Valid bounding boxes
    valid_bbox = validate_bounding_box([0.13, 0.31, 0.87, 0.69])
    assert valid_bbox == [0.13, 0.31, 0.87, 0.69]

    # Non-list/tuple
    with pytest.raises(ValueError, match="Bounding box must be a list or tuple"):
        validate_bounding_box("0.1, 0.2, 0.8, 0.9")  # type: ignore

    # Incorrect number of coordinates
    with pytest.raises(ValueError, match="exactly 4 values"):
        validate_bounding_box([0.1, 0.2, 0.8])

    with pytest.raises(ValueError, match="exactly 4 values"):
        validate_bounding_box([0.1, 0.2, 0.8, 0.9, 0.95])

    # Coordinates out of [0.0, 1.0] range
    with pytest.raises(ValueError, match="out of bounds"):
        validate_bounding_box([-0.05, 0.2, 0.8, 0.9])

    with pytest.raises(ValueError, match="out of bounds"):
        validate_bounding_box([0.1, 0.2, 1.05, 0.9])

    # Inverted coordinates
    with pytest.raises(ValueError, match="x0 .* cannot be greater than x1"):
        validate_bounding_box([0.8, 0.2, 0.1, 0.9])

    with pytest.raises(ValueError, match="y0 .* cannot be greater than y1"):
        validate_bounding_box([0.1, 0.9, 0.8, 0.2])


def test_exact_value_preservation():
    """Verify that cell text and numbers are NEVER silently corrected or modified."""
    raw_headers = [" Raw Header ", "Value with $ and %", "Typo Row"]
    raw_rows = [
        ["  Leading space", "$100.00 M ", "000123"],
        ["Special: © # &", "(50,000)", "Total Debt = 425"],
    ]

    block = extract_table(
        headers=raw_headers,
        rows=raw_rows,
        page=1,
        bbox=[0.0, 0.0, 1.0, 1.0],
        reading_order=1,
    )

    # Every string must be character-for-character identical
    assert block["content"]["headers"] == raw_headers
    assert block["content"]["rows"] == raw_rows

    # Cell-by-cell verification
    assert block["content"]["headers"][0] == " Raw Header "
    assert block["content"]["rows"][0][0] == "  Leading space"
    assert block["content"]["rows"][0][1] == "$100.00 M "
    assert block["content"]["rows"][0][2] == "000123"
    assert block["content"]["rows"][1][1] == "(50,000)"


def test_successful_numeric_validation():
    """Verify consistent component totals result in numeric_consistency_pass."""
    headers = ["Debt Instrument", "Amount"]
    rows = [
        ["Term Loan A", "$100M"],
        ["Term Loan B", "$200M"],
        ["Notes", "$125M"],
        ["Total Debt", "$425M"],
    ]

    block = extract_table(
        headers=headers,
        rows=rows,
        page=31,
        bbox=[0.13, 0.31, 0.87, 0.69],
        reading_order=8,
        block_id="block_042",
    )

    assert "numeric_consistency_pass" in block["risk"]["signals"]
    assert "NUMERIC_INCONSISTENCY" not in block["flags"]
    assert block["flags"] == []
    assert block["risk"]["level"] == "low"
    assert block["risk"]["score"] == 0.12


def test_numeric_inconsistency():
    """Verify mathematical mismatch is flagged with NUMERIC_INCONSISTENCY without mutating text."""
    headers = ["Debt Instrument", "Amount"]
    # 100 + 200 + 125 != 500
    rows = [
        ["Term Loan A", "$100M"],
        ["Term Loan B", "$200M"],
        ["Notes", "$125M"],
        ["Total Debt", "$500M"],
    ]

    block = extract_table(
        headers=headers,
        rows=rows,
        page=31,
        bbox=[0.13, 0.31, 0.87, 0.69],
        reading_order=8,
    )

    # Flag must be present
    assert "NUMERIC_INCONSISTENCY" in block["flags"]
    assert "numeric_consistency_fail" in block["risk"]["signals"]
    assert block["risk"]["level"] == "high"

    # CRITICAL: Raw values in content must remain untouched
    assert block["content"]["rows"][3][1] == "$500M"
    assert block["content"]["rows"][0][1] == "$100M"


def test_accounting_negative_numeric_validation():
    """Verify financial validation with accounting negatives e.g. (100)."""
    headers = ["Line Item", "Amount"]
    rows = [
        ["Revenue", "$1,000"],
        ["Operating Expenses", "($400)"],
        ["Tax", "($100)"],
        ["Net Income", "$500"],
    ]

    block = extract_table(
        headers=headers,
        rows=rows,
        page=1,
        bbox=[0.1, 0.1, 0.9, 0.9],
        reading_order=1,
    )

    assert "numeric_consistency_pass" in block["risk"]["signals"]
    assert "NUMERIC_INCONSISTENCY" not in block["flags"]
    assert block["content"]["rows"][1][1] == "($400)"


# ============================================================================
# Stage 2 Tests: Cross-Page Table Stitching
# ============================================================================

def test_stitch_compatible_tables_consecutive_pages():
    """Verify two compatible tables on consecutive pages are stitched into one."""
    t1 = extract_table(
        headers=["Department", "Expenditure"],
        rows=[["Engineering", "$100M"], ["Research", "$50M"]],
        page=1,
        bbox=[0.1, 0.2, 0.9, 0.8],
        reading_order=1,
        block_id="table_p1",
    )
    t2 = extract_table(
        headers=["Department", "Expenditure"],
        rows=[["Operations", "$75M"], ["Total", "$225M"]],
        page=2,
        bbox=[0.1, 0.1, 0.9, 0.5],
        reading_order=1,
        block_id="table_p2",
    )

    stitched = stitch_tables([t1, t2])

    assert len(stitched) == 1
    merged = stitched[0]

    # Preserves first table's anchor
    assert merged["id"] == "table_p1"
    assert merged["page"] == 1
    assert merged["bbox"] == [0.1, 0.2, 0.9, 0.8]
    assert merged["reading_order"] == 1
    assert merged["extractor"] == "table_engine"

    # Headers and combined rows
    assert merged["content"]["headers"] == ["Department", "Expenditure"]
    assert len(merged["content"]["rows"]) == 4
    assert merged["content"]["rows"] == [
        ["Engineering", "$100M"],
        ["Research", "$50M"],
        ["Operations", "$75M"],
        ["Total", "$225M"],
    ]

    # Stitched signals and successful financial validation across pages
    assert "stitched_cross_page" in merged["risk"]["signals"]
    assert "numeric_consistency_pass" in merged["risk"]["signals"]
    assert "NUMERIC_INCONSISTENCY" not in merged["flags"]


def test_stitch_repeated_continuation_headers_deduplicated():
    """Verify repeated headers on continuation pages are not duplicated in rows."""
    t1 = extract_table(
        headers=["Asset", "Value"],
        rows=[["Cash", "$10M"]],
        page=3,
        bbox=[0.1, 0.2, 0.9, 0.8],
        reading_order=2,
        block_id="tbl_3",
    )
    # Continuation table where the extractor repeated the header row in rows
    t2 = extract_table(
        headers=["Asset", "Value"],
        rows=[["Asset", "Value"], ["Securities", "$20M"]],
        page=4,
        bbox=[0.1, 0.1, 0.9, 0.4],
        reading_order=1,
        block_id="tbl_4",
    )

    stitched = stitch_tables([t1, t2])
    assert len(stitched) == 1

    merged = stitched[0]
    # The duplicate ["Asset", "Value"] row must be skipped
    assert merged["content"]["rows"] == [
        ["Cash", "$10M"],
        ["Securities", "$20M"],
    ]


def test_stitch_incompatible_tables_not_stitched():
    """Verify incompatible tables are kept separate and unmodified."""
    # 1. Non-consecutive pages (page 1 and page 3)
    t_p1 = extract_table(
        headers=["Item", "Cost"],
        rows=[["A", "$10"]],
        page=1,
        bbox=[0.1, 0.1, 0.9, 0.9],
        reading_order=1,
        block_id="t1",
    )
    t_p3 = extract_table(
        headers=["Item", "Cost"],
        rows=[["B", "$20"]],
        page=3,
        bbox=[0.1, 0.1, 0.9, 0.9],
        reading_order=1,
        block_id="t3",
    )
    result_pages = stitch_tables([t_p1, t_p3])
    assert len(result_pages) == 2
    assert result_pages[0]["id"] == "t1"
    assert result_pages[1]["id"] == "t3"

    # 2. Incompatible column counts (2 cols vs 3 cols)
    t_c2 = extract_table(
        headers=["Item", "Cost"],
        rows=[["A", "$10"]],
        page=1,
        bbox=[0.1, 0.1, 0.9, 0.9],
        reading_order=1,
        block_id="tc2",
    )
    t_c3 = extract_table(
        headers=["Item", "Cost", "Quantity"],
        rows=[["B", "$20", "5"]],
        page=2,
        bbox=[0.1, 0.1, 0.9, 0.9],
        reading_order=1,
        block_id="tc3",
    )
    result_cols = stitch_tables([t_c2, t_c3])
    assert len(result_cols) == 2
    assert result_cols[0]["id"] == "tc2"
    assert result_cols[1]["id"] == "tc3"

    # 3. Mismatched headers
    t_h1 = extract_table(
        headers=["Customer", "Balance"],
        rows=[["Alice", "$100"]],
        page=1,
        bbox=[0.1, 0.1, 0.9, 0.9],
        reading_order=1,
        block_id="th1",
    )
    t_h2 = extract_table(
        headers=["Vendor", "Invoice"],
        rows=[["Acme", "$500"]],
        page=2,
        bbox=[0.1, 0.1, 0.9, 0.9],
        reading_order=1,
        block_id="th2",
    )
    result_heads = stitch_tables([t_h1, t_h2])
    assert len(result_heads) == 2


def test_stitch_original_values_remain_unchanged():
    """Verify stitching preserves all raw text, whitespaces, symbols, and formatting."""
    t1 = extract_table(
        headers=[" Line Item ", " Value $ "],
        rows=[["  Raw Entry 1  ", " $100.00 M "]],
        page=1,
        bbox=[0.1, 0.2, 0.8, 0.7],
        reading_order=1,
    )
    t2 = extract_table(
        headers=[" Line Item ", " Value $ "],
        rows=[[" Special © & # ", " (25,000) "]],
        page=2,
        bbox=[0.1, 0.1, 0.8, 0.5],
        reading_order=1,
    )

    stitched = stitch_tables([t1, t2])
    merged = stitched[0]

    # Verify character-by-character preservation
    assert merged["content"]["rows"][0][0] == "  Raw Entry 1  "
    assert merged["content"]["rows"][0][1] == " $100.00 M "
    assert merged["content"]["rows"][1][0] == " Special © & # "
    assert merged["content"]["rows"][1][1] == " (25,000) "


def test_stitch_traceability_fields_valid():
    """Verify traceability fields (traceable, extractor, children linking) remain valid."""
    t1 = extract_table(
        headers=["Col1", "Col2"],
        rows=[["A", "1"]],
        page=1,
        bbox=[0.2, 0.3, 0.7, 0.8],
        reading_order=4,
        block_id="table_alpha",
    )
    t2 = extract_table(
        headers=["Col1", "Col2"],
        rows=[["B", "2"]],
        page=2,
        bbox=[0.2, 0.1, 0.7, 0.4],
        reading_order=1,
        block_id="table_beta",
    )

    stitched = stitch_tables([t1, t2])
    merged = stitched[0]

    assert merged["traceable"] is True
    assert merged["extractor"] == "table_engine"
    assert merged["id"] == "table_alpha"
    # Continuation table ID must be linked in children for provenance
    assert "table_beta" in merged["children"]


# ============================================================================
# Stage 3 Tests: Financial Validation Refinement
# ============================================================================

def test_financial_valid_totals_multiple_currencies_and_nil():
    """Verify correct validation for Euro currency, comma separators, and nil dashes."""
    headers = ["Category", "Amount"]
    rows = [
        ["Hardware", "€1,200.50"],
        ["Licenses", "€799.50"],
        ["Consulting", "-"],  # nil/dash representation
        ["Total", "€2,000.00"],
    ]

    block = extract_table(
        headers=headers,
        rows=rows,
        page=1,
        bbox=[0.1, 0.1, 0.9, 0.9],
        reading_order=1,
    )

    assert "numeric_consistency_pass" in block["risk"]["signals"]
    assert "NUMERIC_INCONSISTENCY" not in block["flags"]
    assert block["risk"]["level"] == "low"
    assert block["risk"]["score"] == 0.12


def test_financial_mismatched_totals_detected():
    """Verify that clear mathematical discrepancy flags NUMERIC_INCONSISTENCY."""
    headers = ["Segment", "Revenue"]
    rows = [
        ["Retail", "$15.5M"],
        ["Enterprise", "$20.0M"],
        ["Government", "$14.5M"],
        ["Grand Total", "$60.0M"],  # Correct sum is 50.0M, discrepancy of 10M
    ]

    block = extract_table(
        headers=headers,
        rows=rows,
        page=1,
        bbox=[0.1, 0.1, 0.9, 0.9],
        reading_order=1,
    )

    assert "NUMERIC_INCONSISTENCY" in block["flags"]
    assert "numeric_consistency_fail" in block["risk"]["signals"]
    assert block["risk"]["level"] == "high"
    # Ensure source text is preserved
    assert block["content"]["rows"][3][1] == "$60.0M"


def test_financial_avoid_false_positives_non_total_rows():
    """
    Verify words like 'Network', 'Consumer', 'Summary', and '% of total'
    are NOT falsely classified as totals.
    """
    # 1. Label contains 'net' within 'Network Equipment'
    assert is_total_row_label("Network Equipment") is False
    assert is_total_row_label("Internet Bandwidth") is False

    # 2. Label contains 'sum' within 'Consumer' or 'Summary'
    assert is_total_row_label("Consumer Discretionary") is False
    assert is_total_row_label("Summary of Accounts") is False
    assert is_total_row_label("Assumption Case 1") is False

    # 3. Ratio or percent of total is not a total row
    assert is_total_row_label("% of Total") is False
    assert is_total_row_label("Share of Total") is False

    # Table with 'Network Equipment' should NOT trigger numeric consistency pass or fail
    headers = ["Category", "Expenditure"]
    rows = [
        ["Servers", "$100M"],
        ["Storage", "$200M"],
        ["Network Equipment", "$50M"],  # 100 + 200 != 50, but this is NOT a total!
    ]

    block = extract_table(
        headers=headers,
        rows=rows,
        page=1,
        bbox=[0.1, 0.1, 0.9, 0.9],
        reading_order=1,
    )

    # Must NOT have numeric inconsistency flag or pass signal because no total exists
    assert "NUMERIC_INCONSISTENCY" not in block["flags"]
    assert "numeric_consistency_fail" not in block["risk"]["signals"]
    assert "numeric_consistency_pass" not in block["risk"]["signals"]
    assert block["flags"] == []
    assert block["risk"]["level"] == "low"


def test_financial_positive_total_keywords():
    """Verify clear total keywords are properly recognized."""
    assert is_total_row_label("Total") is True
    assert is_total_row_label("Total Debt") is True
    assert is_total_row_label("Grand Total") is True
    assert is_total_row_label("Subtotal") is True
    assert is_total_row_label("Sum") is True
    assert is_total_row_label("Aggregate") is True
    assert is_total_row_label("Net Income") is True
    assert is_total_row_label("Net Debt") is True
