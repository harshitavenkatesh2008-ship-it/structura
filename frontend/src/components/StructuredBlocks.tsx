import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlignLeft,
  ArrowUpRight,
  Braces,
  ChartColumn,
  Heading,
  Image,
  Layers3,
  List,
  Search,
  Sigma,
  Table2,
} from "lucide-react";
import type { Block, BlockType, Document } from "../types/document";
import { getBlocks } from "../utils/document";
import { RiskBadge, TraceBadge } from "./UI";

const typeIcons = {
  heading: Heading,
  paragraph: AlignLeft,
  list: List,
  table: Table2,
  figure: Layers3,
  chart: ChartColumn,
  equation: Sigma,
  image: Image,
};
const types: BlockType[] = [
  "heading",
  "paragraph",
  "list",
  "table",
  "figure",
  "chart",
  "equation",
  "image",
];

export function StructuredBlocks({
  document,
  selected,
  onSelect,
  traceRequest = 0,
}: {
  document: Document;
  selected: Block | null;
  onSelect: (block: Block) => void;
  traceRequest?: number;
}) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("all");
  const scrollPane = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (traceRequest === 0) return;
    setQuery("");
    setType("all");
  }, [traceRequest]);
  const blocks = useMemo(
    () =>
      getBlocks(document).filter(
        (block) =>
          (type === "all" || type === block.type) &&
          `${block.content} ${block.id}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [document, query, type],
  );
  useEffect(() => {
    const pane = scrollPane.current;
    const card = pane?.querySelector<HTMLButtonElement>(".block-card.selected");
    if (!pane || !card) return;
    // Scroll only the block list, so the linked source page stays in place.
    pane.scrollTop +=
      card.getBoundingClientRect().top - pane.getBoundingClientRect().top - 16;
  }, [selected?.id, blocks]);
  return (
    <section className="structured-panel panel" aria-label="Structured output">
      <div className="viewer-heading">
        <div>
          <Braces size={16} />
          <strong>Structured output</strong>
        </div>
        <span>{document.metrics.block_count} BLOCKS</span>
      </div>
      <div className="block-toolbar">
        <label className="search-input">
          <Search size={15} />
          <input
            aria-label="Search extracted blocks"
            placeholder="Search blocks…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <select
          aria-label="Filter block type"
          value={type}
          onChange={(event) => setType(event.target.value)}
        >
          <option value="all">All types</option>
          {types.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </div>
      <div className="block-scroll" ref={scrollPane}>
        {blocks.length === 0 && (
          <div className="empty-results">
            No blocks match your search.
            <button
              className="button text-button"
              onClick={() => {
                setQuery("");
                setType("all");
              }}
            >
              Clear filters
            </button>
          </div>
        )}
        {blocks.map((block, index) => {
          const Icon = typeIcons[block.type];
          return (
            <div key={block.id}>
              {(index === 0 || blocks[index - 1].page !== block.page) && (
                <div className="block-page-label">
                  <span>PAGE {String(block.page).padStart(2, "0")}</span>
                  <span>READING ORDER</span>
                </div>
              )}
              <button
                className={`block-card ${selected?.id === block.id ? "selected" : ""} ${block.parent ? "child-block" : ""}`}
                aria-pressed={selected?.id === block.id}
                onClick={() => onSelect(block)}
                data-testid={`block-${block.id}`}
              >
                <div className="block-card-top">
                  <span className="block-type">
                    <Icon size={13} />
                    {block.type}
                    {block.parent && <small> / total row</small>}
                  </span>
                  <code className="block-id">{block.id}</code>
                  <RiskBadge risk={block.risk} />
                </div>
                <div className={`block-content content-${block.type}`}>
                  {block.table ? (
                    <>
                      <strong>{block.content}</strong>
                      <div className="output-table">
                        <div className="output-table-row table-header">
                          {block.table.headers.map((cell) => (
                            <span key={cell}>{cell}</span>
                          ))}
                        </div>
                        {block.table.rows.map((row) => (
                          <div className="output-table-row" key={row[0]}>
                            {row.map((cell) => (
                              <span key={cell}>{cell}</span>
                            ))}
                          </div>
                        ))}
                      </div>
                    </>
                  ) : block.type === "list" ? (
                    <ul>
                      {block.content.split("\n").map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    block.content
                  )}
                </div>
                <div className="block-card-bottom">
                  <span className="block-source-page">page {block.page}</span>
                  <span
                    className="extractor-label"
                    title="Authored extractor label in the mock Document Graph; no extraction engine ran"
                  >
                    {block.extractor}
                  </span>
                  <TraceBadge traceable={block.traceable} />
                  <ArrowUpRight className="block-open" size={13} />
                </div>
              </button>
            </div>
          );
        })}
      </div>
      <div className="structured-footer">
        <span>{blocks.length} blocks shown</span>
        <span>Click any block to trace its source</span>
      </div>
    </section>
  );
}
