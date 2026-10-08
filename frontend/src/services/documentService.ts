import { mockDocument } from "../data/mockDocument";
import type { Document, Block, Page } from "../types/document";

const API_BASE = "http://127.0.0.1:8000";

export interface DocumentService {
  getDocument(): Document | Promise<Document>;
  processDocument(file: File): Promise<Document>;
}

interface ApiResponse<T> {
  status: string;
  message?: string;
  data?: T;
  errors?: unknown[];
  meta?: {
    pipeline_status?: string;
    block_count?: number;
  };
}

interface IngestData {
  document_id: string;
  filename: string;
  format: string;
  content_type: string;
  size_bytes: number;
  status: string;
  storage_key: string;
}

interface BackendBlock {
  id: string;
  type: Block["type"];
  page: number;
  bbox: [number, number, number, number];
  reading_order: number;
  content: {
    text?: string;
    [key: string]: unknown;
  };
  extractor: Block["extractor"];
  risk: {
    score?: number;
    level?: Block["risk"];
    signals?: string[];
  };
  confidence?: number | null;
  flags?: string[];
  traceable?: boolean;
  parent?: string | null;
  children?: string[];
}

interface BackendPage {
  page: number;
  width: number;
  height: number;
  blocks: BackendBlock[];
}

interface BackendDocument {
  document_id: string;
  filename: string;
  format: string;
  page_count: number;
  pages: BackendPage[];
  metrics?: {
    processing_time_seconds?: number;
    pages_per_second?: number;
    provenance_coverage?: number | null;
    escalated_regions_percent?: number | null;
    estimated_cost_per_1000_pages?: number | null;
    cost_per_correct_page?: number | null;
  };
}

interface ProcessData {
  graph: BackendDocument;
  graph_ref?: {
    schema_version: string;
    revision: string;
    url: string;
  };
  quality?: {
    completeness?: string;
    fidelity?: string;
    confidence?: number | null;
    risk?: string | null;
  };
}

function mapBlock(block: BackendBlock): Block {
  return {
    id: block.id,
    type: block.type,
    page: block.page,
    bbox: block.bbox,
    content: block.content?.text ?? "",
    extractor: block.extractor,
    risk: block.risk?.level ?? "low",
    flags: block.flags ?? [],
    traceable: block.traceable ?? false,
    parent: block.parent ?? null,
    children: block.children ?? [],
  };
}

function mapDocument(
  graph: BackendDocument,
  pipelineStatus?: string,
): Document {
  const pages: Page[] = graph.pages.map((page) => ({
    page: page.page,
    width: page.width,
    height: page.height,
    blocks: page.blocks.map(mapBlock),
  }));

  const blocks = pages.flatMap((page) => page.blocks);

  return {
    document_id: graph.document_id,
    filename: graph.filename,
    format: graph.format,
    status: pipelineStatus === "processing" ? "processing" : "ready",
    pipeline_status: pipelineStatus,
    page_count: graph.page_count,
    pages,
    metrics: {
      block_count: blocks.length,
      traceable_blocks: blocks.filter((block) => block.traceable).length,
      review_blocks: blocks.filter((block) => block.risk !== "low").length,
    },
  };
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<ApiResponse<T>> {
  const response = await fetch(`${API_BASE}${path}`, options);

  if (!response.ok) {
    const body = await response.text();
    throw new Error(
      `STRUCTURA API request failed (${response.status}): ${body}`,
    );
  }

  return response.json() as Promise<ApiResponse<T>>;
}

export const documentService: DocumentService = {
  getDocument: () => mockDocument,

  async processDocument(file: File): Promise<Document> {
    const formData = new FormData();
    formData.append("file", file);

    const ingest = await request<IngestData>("/v1/ingest", {
      method: "POST",
      body: formData,
    });

    if (!ingest.data?.document_id) {
      throw new Error("Upload succeeded but no document_id was returned.");
    }

    const documentId = ingest.data.document_id;

    const processed = await request<ProcessData>(
      `/v1/documents/${documentId}/process`,
      {
        method: "POST",
      },
    );

    if (!processed.data?.graph) {
      throw new Error("Processing succeeded but no Document Graph was returned.");
    }

    return mapDocument(
      processed.data.graph,
      processed.meta?.pipeline_status ?? "unknown",
    );
  },
};
