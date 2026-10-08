import type { Block, Document, Page } from "../types/document";

// Every value is authored demo content, not an extraction or benchmark result.
function block(
  input: Pick<Block, "id" | "type" | "page" | "bbox" | "content"> &
    Partial<Block>,
): Block {
  return {
    extractor: "native_pdf",
    risk: "low",
    flags: [],
    traceable: true,
    parent: null,
    children: [],
    ...input,
  };
}

const pages: Page[] = [
  {
    page: 1,
    width: 612,
    height: 792,
    blocks: [
      block({
        id: "block_001",
        type: "heading",
        page: 1,
        bbox: [0.1, 0.13, 0.9, 0.23],
        content: "Northstar Acquisition\nTransaction overview",
      }),
      block({
        id: "block_002",
        type: "paragraph",
        page: 1,
        bbox: [0.1, 0.27, 0.9, 0.39],
        content:
          "Northstar Holdings proposes the acquisition of Meridian Industrial Group, a diversified manufacturer serving infrastructure and specialty equipment markets. This report summarizes the proposed transaction and illustrative financing structure.",
      }),
      block({
        id: "block_003",
        type: "heading",
        page: 1,
        bbox: [0.1, 0.43, 0.9, 0.47],
        content: "01  Investment rationale",
      }),
      block({
        id: "block_004",
        type: "list",
        page: 1,
        bbox: [0.1, 0.5, 0.9, 0.65],
        content:
          "Complementary product portfolios and customer relationships\nExpansion of regional manufacturing capabilities\nA shared platform for long-term operational development",
      }),
      block({
        id: "block_005",
        type: "figure",
        page: 1,
        bbox: [0.1, 0.69, 0.9, 0.82],
        content:
          "Transaction structure: Northstar Holdings → Meridian Industrial Group",
        extractor: "vision_engine",
        risk: "medium",
        flags: ["illustrative_diagram"],
      }),
      block({
        id: "block_006",
        type: "paragraph",
        page: 1,
        bbox: [0.1, 0.85, 0.9, 0.9],
        content:
          "Financing details are set out on the following page. All amounts and companies in this report are fictional.",
      }),
    ],
  },
  {
    page: 2,
    width: 612,
    height: 792,
    blocks: [
      block({
        id: "block_007",
        type: "heading",
        page: 2,
        bbox: [0.1, 0.13, 0.9, 0.22],
        content: "Acquisition financing\nSources of debt capital",
      }),
      block({
        id: "block_008",
        type: "paragraph",
        page: 2,
        bbox: [0.1, 0.26, 0.9, 0.36],
        content:
          "The illustrative financing package combines senior term loans and notes. The schedule below reconciles the individual facilities to the total debt funding requirement. Amounts are in USD millions.",
      }),
      block({
        id: "block_009",
        type: "table",
        page: 2,
        bbox: [0.1, 0.4, 0.9, 0.65],
        content: "Debt financing schedule",
        extractor: "table_engine",
        children: ["block_010"],
        table: {
          headers: ["Debt instrument", "Amount"],
          rows: [
            ["Term Loan A", "$100M"],
            ["Term Loan B", "$200M"],
            ["Notes", "$125M"],
            ["Total Debt", "$425M"],
          ],
        },
      }),
      // The row occupies the final fifth of the parent table: exact shared geometry.
      block({
        id: "block_010",
        type: "table",
        page: 2,
        bbox: [0.1, 0.6, 0.9, 0.65],
        content: "Total Debt — $425M",
        extractor: "table_engine",
        parent: "block_009",
        flags: ["total_row"],
      }),
      block({
        id: "block_011",
        type: "equation",
        page: 2,
        bbox: [0.1, 0.7, 0.9, 0.76],
        content: "Total debt = $100M + $200M + $125M = $425M",
        extractor: "math_engine",
        risk: "medium",
        flags: ["review_notation"],
      }),
      block({
        id: "block_012",
        type: "paragraph",
        page: 2,
        bbox: [0.1, 0.8, 0.9, 0.89],
        content:
          "The debt schedule is illustrative only. Facility terms, maturity dates and pricing are outside the scope of this mock report. Refer to the source schedule when interpreting the total.",
      }),
    ],
  },
  {
    page: 3,
    width: 612,
    height: 792,
    blocks: [
      block({
        id: "block_013",
        type: "heading",
        page: 3,
        bbox: [0.1, 0.13, 0.9, 0.23],
        content: "Supporting analysis\nCapital structure & review notes",
      }),
      block({
        id: "block_014",
        type: "chart",
        page: 3,
        bbox: [0.1, 0.27, 0.9, 0.45],
        content:
          "Illustrative debt mix: Term Loan A $100M · Term Loan B $200M · Notes $125M",
        extractor: "vision_engine",
        risk: "medium",
        flags: ["chart_labels_review"],
      }),
      block({
        id: "block_015",
        type: "heading",
        page: 3,
        bbox: [0.1, 0.5, 0.9, 0.54],
        content: "03  Review considerations",
      }),
      block({
        id: "block_016",
        type: "list",
        page: 3,
        bbox: [0.1, 0.57, 0.9, 0.7],
        content:
          "Confirm facility definitions against the financing schedule\nReview diagram labels and mathematical notation\nObtain the original approval stamp before relying on it",
        risk: "medium",
        flags: ["manual_review"],
      }),
      block({
        id: "block_017",
        type: "image",
        page: 3,
        bbox: [0.1, 0.74, 0.45, 0.85],
        content: "Scanned approval stamp — source mapping unavailable",
        extractor: "ocr",
        risk: "high",
        traceable: false,
        flags: ["unresolved_source_mapping", "low_quality_scan"],
      }),
      block({
        id: "block_018",
        type: "paragraph",
        page: 3,
        bbox: [0.1, 0.88, 0.9, 0.93],
        content:
          "Prepared as a fictional demonstration of source-connected document structure. Not investment advice or a real transaction report.",
      }),
    ],
  },
];

const allBlocks = pages.flatMap((page) => page.blocks);
export const mockDocument: Document = {
  document_id: "doc_northstar_demo",
  filename: "Northstar_Acquisition_Report.pdf",
  format: "PDF",
  status: "ready",
  page_count: pages.length,
  pages,
  metrics: {
    block_count: allBlocks.length,
    traceable_blocks: allBlocks.filter((block) => block.traceable).length,
    review_blocks: allBlocks.filter((block) => block.risk !== "low").length,
  },
};

export const DEMO_DEBT_ID = "block_010";
export const reportTitle = "Northstar Acquisition Report";
