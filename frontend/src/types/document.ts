/** Normalized coordinates [left, top, right, bottom], origin at top-left. */
export type BoundingBox = [number, number, number, number];
export type Risk = "low" | "medium" | "high";
export type Extractor =
  | "native_pdf"
  | "ocr"
  | "table_engine"
  | "vision_engine"
  | "math_engine";
export type BlockType =
  | "heading"
  | "paragraph"
  | "list"
  | "table"
  | "figure"
  | "chart"
  | "equation"
  | "image";

export interface Block {
  id: string;
  type: BlockType;
  page: number;
  bbox: BoundingBox;
  content: string;
  extractor: Extractor;
  risk: Risk;
  flags: string[];
  traceable: boolean;
  parent: string | null;
  children: string[];
  /** Optional display metadata for mock table content. */
  table?: { headers: string[]; rows: string[][] };
}

export interface Page {
  page: number;
  width: number;
  height: number;
  blocks: Block[];
}

export interface Document {
  document_id: string;
  filename: string;
  format: string;
  status: "ready" | "processing";
  page_count: number;
  pages: Page[];
  metrics: {
    block_count: number;
    traceable_blocks: number;
    review_blocks: number;
  };
}

export type View =
  | "overview"
  | "document"
  | "structured"
  | "markdown"
  | "json"
  | "analytics"
  | "upload"
  | "processing";
