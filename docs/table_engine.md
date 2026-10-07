# Structura Table Engine (P4) Documentation

The Table Engine (`table_engine`) is the specialized document ingestion component responsible for converting structured table data into compliant **Structura Document Graph v1.0** table blocks, performing financial and numeric consistency checks, and stitching continuation tables across consecutive pages.

---

## 1. Purpose

The Table Engine serves three core responsibilities in the Structura pipeline:
1. **Document Graph Transformation**: Converts pre-extracted tabular cell data, headers, and spatial coordinates into normalized, traceable Document Graph v1.0 blocks with standardized extractor identity (`"table_engine"`).
2. **Provenance & Invariance Enforcement**: Strictly enforces the universal Structura invariant: **never silently modify, autocorrect, or normalize extracted cell text or numbers**.
3. **Numeric Validation & Stitching**: Analyzes table components against stated totals (flagging discrepancies without mutating data) and stitches continuation tables across consecutive pages while preserving anchor provenance.

> [!NOTE]
> The Table Engine processes structured tabular structures (lists of headers, rows, page indices, and bounding boxes). It does **not** directly perform raw PDF stream parsing, optical character recognition (OCR), or visual bounding-box layout segmentation; these are expected from upstream components (such as Document Parser and Safe Router).

---

## 2. Input Format

The primary extraction interfaces are `TableEngine.extract()` and the convenience helper `extract_table()` in [`backend/app/extractors/table_engine.py`](file:///c:/Users/HAI/Desktop/Structura-TableEngine/structura/backend/app/extractors/table_engine.py).

### Parameters

| Parameter | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `headers` | `List[str]` | Yes | Ordered list of column header strings. |
| `rows` | `List[List[str]]` | Yes | 2D list of row cell strings. |
| `page` | `int` | Yes | 1-based positive integer indicating the document page. |
| `bbox` | `Sequence[Union[int, float]]` | Yes | 4-element sequence `[x0, y0, x1, y1]` representing normalized coordinates in `[0.0, 1.0]` with top-left origin. |
| `reading_order` | `int` | Yes | Logical sequential order index within the page. |
| `block_id` | `Optional[str]` | No | Unique identifier for the block (auto-generated if omitted, e.g. `block_<uuid>`). |
| `confidence` | `Optional[float]` | No | Detection confidence score (defaults to `None`). |
| `parent` | `Optional[str]` | No | Identifier of the parent block (defaults to `None`). |
| `children` | `Optional[List[str]]` | No | Identifiers of child or continuation blocks (defaults to `[]`). |

---

## 3. Output Format

The output is a Python dictionary strictly complying with the **Document Graph v1.0 Block** schema defined in [`docs/document_graph.md`](file:///c:/Users/HAI/Desktop/Structura-TableEngine/structura/docs/document_graph.md):

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `str` | Unique block identifier. |
| `type` | `str` | Strictly `"table"`. |
| `page` | `int` | Source page number (1-based integer). |
| `bbox` | `List[float]` | Normalized bounding box `[x0, y0, x1, y1]` where all values are in `[0.0, 1.0]`. |
| `reading_order` | `int` | Reading order index. |
| `content` | `dict` | Object containing verbatim `headers` (`List[str]`) and `rows` (`List[List[str]]`). |
| `extractor` | `str` | Strictly `"table_engine"`. |
| `risk` | `dict` | Evidence-based risk assessment: `score` (`float`), `level` (`"low"`, `"medium"`, or `"high"`), and `signals` (`List[str]`). |
| `confidence` | `Optional[float]` | Upstream confidence value or `None`. |
| `flags` | `List[str]` | List of error/warning flags, e.g. `["NUMERIC_INCONSISTENCY"]`. |
| `traceable` | `bool` | Strictly `True` (enables Structura TraceBack). |
| `parent` | `Optional[str]` | Parent block identifier or `None`. |
| `children` | `List[str]` | List of related or continuation block IDs. |

---

## 4. Confidence and Risk Information

In Structura, risk is evidence-based and is not treated as a calibrated probability:

* **Baseline State**:
  * `score`: `0.12`
  * `level`: `"low"`
  * `signals`: `[]` (or `["numeric_consistency_pass"]` when verified)
  * `flags`: `[]`
* **Numeric Pass**:
  * When stated totals match the sum of component rows within numerical tolerance, the signal `"numeric_consistency_pass"` is appended to `risk.signals`. Risk score remains `0.12` (`"low"`).
* **Numeric Inconsistency**:
  * When a stated total contradicts component sums, `risk.score` is set to `0.70`, `risk.level` becomes `"high"`, signal `"numeric_consistency_fail"` is recorded, and the flag `"NUMERIC_INCONSISTENCY"` is appended to `flags`.
* **Stitched Continuity**:
  * When continuation tables are merged across pages, the signal `"stitched_cross_page"` is added to `risk.signals`.

---

## 5. Failure Cases and Validation Behavior

The engine strictly validates input geometry and structures:

1. **Page Index Validation**:
   * Must be an integer `>= 1`. Non-integer or non-positive values raise `ValueError`.
2. **Bounding Box Validation (`validate_bounding_box`)**:
   * Must be a list or tuple containing **exactly 4 numeric values**.
   * All coordinates must satisfy `0.0 <= coord <= 1.0`.
   * Enforces top-left origin convention: `x0 <= x1` and `y0 <= y1`.
   * Violations raise `ValueError` describing the specific out-of-bounds or inverted coordinate condition.
3. **No Silent Correction Rule**:
   * If numbers in a table fail to add up, or strings contain unusual formatting, the Table Engine **never** modifies or recalculates cell values. The raw strings remain untouched, and the discrepancy is logged in `flags` and `risk.signals`.

---

## 6. Cross-Page Table Stitching

Multi-page tables are handled by `stitch_tables()` and `stitch_two_tables()` in [`backend/app/extractors/table_engine.py`](file:///c:/Users/HAI/Desktop/Structura-TableEngine/structura/backend/app/extractors/table_engine.py).

### Compatibility Criteria
Two table blocks are eligible for stitching if:
* Both blocks have `type == "table"`.
* Pages are strictly consecutive (`table2.page == table1.last_page + 1`).
* Column counts match (`len(headers1) == len(headers2)` or identical row lengths).
* Headers are compatible (case-insensitive stripped match, or continuation table omits headers).

### Stitching Behavior
* **Anchor Preservation**: The first table's `id`, `page`, `bbox`, `reading_order`, and `extractor` are preserved as the primary anchor block.
* **Row Concatenation**: Continuation rows are appended in document reading order.
* **Header Deduplication**: If continuation rows start with a duplicate of the header row, that duplicate row is automatically skipped.
* **Traceability Preservation**: The second table's ID (`table2["id"]`) is linked into the anchor block's `children` list, maintaining full provenance for Structura TraceBack.
* **Re-validation**: Financial validation is re-evaluated across the full stitched row set, and the `"stitched_cross_page"` signal is added.
* **Incompatible Tables**: If tables do not satisfy the structural compatibility criteria, they remain separate and unmodified.

---

## 7. Financial Validation

The financial validation logic resides in [`backend/app/validators/financial.py`](file:///c:/Users/HAI/Desktop/Structura-TableEngine/structura/backend/app/validators/financial.py).

### Numeric Parsing (`parse_numeric_cell`)
Parses financial strings into floating-point numbers without altering the original strings:
* **Currency Symbols**: Strips `$`, `€`, `£`, `¥`, `₹`.
* **Negatives**: Supports standard minus (`-100`) and accounting parentheses (`(100)` or `($50M)`).
* **Metric Suffixes**: Handles `K` ($10^3$), `M` ($10^6$), `B` ($10^9$), `T` ($10^{12}$), and `%` ($0.01$).
* **Separators**: Removes commas in numbers like `1,000,000`.
* **Nil Balances**: Recognizes financial dashes (`"-"`, `"–"`, `"—”`, `"nil"`) as `0.0`.

### Total Row Detection & False-Positive Elimination
* **Regex Word Boundaries**: Uses strict word boundaries (`\b(grand total|subtotal|total)\b`, `^(sum|aggregate)\b`, `\bnet\s+(income|loss|profit|total|debt|amount)\b`, `^net\b`).
* **Exclusion Filters**: Excludes ratio labels like `"% of Total"` or `"Share of Total"`.
* **Word Boundary Guard**: Avoids false matches within regular words (e.g., `"Network Equipment"`, `"Consumer Staples"`, or `"Summary of Accounts"`).

### Component Calculation
* Identifies at least 2 numeric component values located above the total line in that column.
* Calculates component sums and checks equality with stated totals using tolerance `max(1e-4, abs(total) * 1e-4)`.
* Emits `"numeric_consistency_pass"` if all totals match.
* Emits `"numeric_consistency_fail"` and `"NUMERIC_INCONSISTENCY"` if any stated total does not match.

---

## 8. Sample Input

```python
from backend.app.extractors.table_engine import extract_table

headers = ["Debt Instrument", "Amount"]
rows = [
    ["Term Loan A", "$100M"],
    ["Term Loan B", "$200M"],
    ["Notes", "$125M"],
    ["Total Debt", "$425M"]
]
bbox = [0.13, 0.31, 0.87, 0.69]

table_block = extract_table(
    headers=headers,
    rows=rows,
    page=31,
    bbox=bbox,
    reading_order=8,
    block_id="block_042"
)
```

---

## 9. Sample Document Graph Table Output

```json
{
  "id": "block_042",
  "type": "table",
  "page": 31,
  "bbox": [0.13, 0.31, 0.87, 0.69],
  "reading_order": 8,
  "content": {
    "headers": [
      "Debt Instrument",
      "Amount"
    ],
    "rows": [
      ["Term Loan A", "$100M"],
      ["Term Loan B", "$200M"],
      ["Notes", "$125M"],
      ["Total Debt", "$425M"]
    ]
  },
  "extractor": "table_engine",
  "risk": {
    "score": 0.12,
    "level": "low",
    "signals": [
      "numeric_consistency_pass"
    ]
  },
  "confidence": null,
  "flags": [],
  "traceable": true,
  "parent": null,
  "children": []
}
```

---

## 10. Current Limitations / Boundaries

1. **Upstream Ingestion Dependency**: The module does not detect bounding boxes or perform OCR directly on binary PDF or image files. It relies on upstream extractors/routers to supply structured tables.
2. **Column-0 Labeling Assumption**: Total row detection expects primary labels (e.g. `"Total"`, `"Net Income"`) to reside in the first column (`row[0]`).
3. **Sequential Page Flow**: Stitching assumes sequential page order (`page + 1`) and does not reassemble non-consecutive or multi-column newspaper layouts.
4. **Summation Only**: Financial consistency validation verifies additive column summations; it does not evaluate row-wise operations (e.g., `Units * Rate = Total`) or complex formula calculations.
