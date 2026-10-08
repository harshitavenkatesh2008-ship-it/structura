import { mockDocument } from "../data/mockDocument";
import type { Document } from "../types/document";

/** A future API adapter only needs to return the same Document shape. */
export interface DocumentService {
  getDocument(): Document | Promise<Document>;
}

// No requests, file ingestion or extraction happens in this implementation.
export const documentService: DocumentService = {
  getDocument: () => mockDocument,
};
