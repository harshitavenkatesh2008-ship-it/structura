import { useState } from "react";
import { Braces, ChevronDown, ChevronRight, FileText } from "lucide-react";
import type { Document } from "../types/document";
import { Badge, MockNotice, PageHeading } from "./UI";
import { CodeViewer, JsonTokens, OutputActions } from "./OutputViewer";

type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };
function TreeNode({
  name,
  value,
  depth = 0,
}: {
  name: string;
  value: JsonValue;
  depth?: number;
}) {
  const [open, setOpen] = useState(depth < 2);
  const expandable = value !== null && typeof value === "object";
  const entries = expandable ? Object.entries(value) : [];
  return (
    <div className="json-tree-node">
      {expandable ? (
        <>
          <button
            className="json-tree-toggle"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            <span className="json-key">{name}</span>
            <span className="json-punctuation">
              {Array.isArray(value) ? "[" : "{"}
            </span>
            <small>
              {entries.length} {Array.isArray(value) ? "items" : "keys"}
            </small>
            <span className="json-punctuation">
              {!open && (Array.isArray(value) ? "]" : "}")}
            </span>
          </button>
          {open && (
            <div className="json-tree-children">
              {entries.map(([key, item]) => (
                <TreeNode key={key} name={key} value={item} depth={depth + 1} />
              ))}
              <div className="json-tree-close">
                {Array.isArray(value) ? "]" : "}"}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="json-tree-leaf">
          <JsonTokens
            line={`${JSON.stringify(name)}: ${JSON.stringify(value)}`}
          />
        </div>
      )}
    </div>
  );
}

export function JSONViewer({ document }: { document: Document }) {
  const [mode, setMode] = useState<"raw" | "tree">("raw");
  const [page, setPage] = useState("all");
  const [blockId, setBlockId] = useState("all");
  const activePage = document.pages.find((item) => String(item.page) === page);
  const activeBlock = activePage?.blocks.find((item) => item.id === blockId);
  const inspected = activeBlock ?? activePage ?? document;
  const content = JSON.stringify(document, null, 2);
  return (
    <div className="page-content">
      <PageHeading
        eyebrow="OUTPUT / DOCUMENT GRAPH"
        title="The whole document. Structured."
        description="Pages, blocks, coordinates, and relationships in one inspectable graph."
        action={
          <OutputActions
            content={content}
            filename="northstar-document-graph.json"
            type="application/json"
          />
        }
      />
      <div className="panel output-panel">
        <div className="viewer-heading">
          <div>
            <Braces size={17} />
            <strong>document_graph.json</strong>
            <Badge>JSON</Badge>
          </div>
          <div
            className="segmented"
            role="group"
            aria-label="JSON display mode"
          >
            <button
              className={mode === "raw" ? "active" : ""}
              aria-pressed={mode === "raw"}
              onClick={() => setMode("raw")}
            >
              Raw JSON
            </button>
            <button
              className={mode === "tree" ? "active" : ""}
              aria-pressed={mode === "tree"}
              onClick={() => setMode("tree")}
            >
              Tree
            </button>
          </div>
        </div>
        <div className="json-inspector-toolbar">
          <div>
            <FileText size={13} />
            <label htmlFor="json-page">Scope</label>
            <select
              id="json-page"
              aria-label="JSON source page"
              value={page}
              onChange={(event) => {
                setPage(event.target.value);
                setBlockId("all");
              }}
            >
              <option value="all">Whole document</option>
              {document.pages.map((item) => (
                <option key={item.page} value={item.page}>
                  Page {item.page}
                </option>
              ))}
            </select>
            {activePage && (
              <select
                aria-label="JSON block"
                value={blockId}
                onChange={(event) => setBlockId(event.target.value)}
              >
                <option value="all">All page blocks</option>
                {activePage.blocks.map((block) => (
                  <option key={block.id} value={block.id}>
                    {block.id} · {block.type}
                  </option>
                ))}
              </select>
            )}
          </div>
          <span>
            {document.metrics.block_count} BLOCKS · {document.page_count} PAGES
          </span>
        </div>
        {mode === "raw" ? (
          <CodeViewer
            content={JSON.stringify(inspected, null, 2)}
            language="json"
          />
        ) : (
          <div className="json-tree" aria-label="Document Graph tree">
            <TreeNode
              key={`${page}-${blockId}`}
              name={
                activeBlock?.id ??
                (activePage ? `page_${activePage.page}` : "document_graph")
              }
              value={JSON.parse(JSON.stringify(inspected)) as JsonValue}
            />
          </div>
        )}
        <div className="output-footer">
          <code>{document.document_id}</code>
          <span>
            Normalized coordinates · Exports always include the complete graph
          </span>
        </div>
      </div>
      <MockNotice />
    </div>
  );
}
