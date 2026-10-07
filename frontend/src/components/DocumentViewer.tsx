import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Link2,
  Minus,
  Plus,
  ScanLine,
} from "lucide-react";
import { useState } from "react";
import type { Ref } from "react";
import type { Block, Document, Page } from "../types/document";
import { reportTitle } from "../data/mockDocument";

function SourceContent({ block }: { block: Block }) {
  if (block.table)
    return (
      <div className="source-table">
        <div className="source-table-row source-table-head">
          {block.table.headers.map((cell) => (
            <span key={cell}>{cell}</span>
          ))}
        </div>
        {block.table.rows.map((row, index) => (
          <div
            className={`source-table-row ${index === block.table!.rows.length - 1 ? "total-row" : ""}`}
            key={row[0]}
          >
            {row.map((cell) => (
              <span key={cell}>{cell}</span>
            ))}
          </div>
        ))}
      </div>
    );
  if (block.type === "list")
    return (
      <ul>
        {block.content.split("\n").map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );
  if (block.type === "figure")
    return (
      <div className="source-figure">
        <span>
          Northstar
          <br />
          <strong>Holdings</strong>
        </span>
        <span className="figure-arrow">→</span>
        <span>
          Meridian
          <br />
          <strong>Industrial Group</strong>
        </span>
        <small>ILLUSTRATIVE TRANSACTION STRUCTURE</small>
      </div>
    );
  if (block.type === "chart")
    return (
      <div className="source-chart">
        <small>ILLUSTRATIVE DEBT MIX · USD MILLIONS</small>
        {[
          ["Term Loan A", 100],
          ["Term Loan B", 200],
          ["Notes", 125],
        ].map(([label, amount]) => (
          <div key={label}>
            <span>{label}</span>
            <i style={{ width: `${(Number(amount) / 250) * 55}%` }} />
            <b>${amount}M</b>
          </div>
        ))}
      </div>
    );
  if (block.type === "image")
    return (
      <div className="source-stamp">
        COPY
        <br />
        <small>STAMP NOT VERIFIED</small>
      </div>
    );
  return (
    <>
      {block.content.split("\n").map((line, index) => (
        <span className={index === 1 ? "source-subtitle" : ""} key={line}>
          {line}
          {index === 0 && block.content.includes("\n") && <br />}
        </span>
      ))}
    </>
  );
}

const regionStyle = (block: Block) => ({
  left: `${block.bbox[0] * 100}%`,
  top: `${block.bbox[1] * 100}%`,
  width: `${(block.bbox[2] - block.bbox[0]) * 100}%`,
  height: `${(block.bbox[3] - block.bbox[1]) * 100}%`,
});

/** The same graph and source geometry power the overview preview and inspection viewer. */
export function SourcePage({
  page,
  selected,
  showRegions = false,
  onSelect,
}: {
  page: Page;
  selected: Block | null;
  showRegions?: boolean;
  onSelect?: (block: Block) => void;
}) {
  const showOverlay = selected?.traceable && selected.page === page.page;
  return (
    <div
      className={`document-paper ${showRegions ? "show-regions" : ""}`}
      style={{ aspectRatio: `${page.width} / ${page.height}` }}
      data-testid="document-paper"
    >
      <div className="paper-header">
        <span>NORTHSTAR</span>
        <span>TRANSACTION REPORT / DEMO</span>
      </div>
      {page.blocks
        .filter((block) => !block.parent)
        .map((block) => (
          <div
            key={block.id}
            className={`source-block source-${block.type} ${block.type === "heading" && block.bbox[1] > 0.3 ? "section-heading" : ""} ${block.traceable ? "mapped-region" : "unmapped-region"} ${onSelect ? "selectable-source" : ""}`}
            style={regionStyle(block)}
            role={onSelect ? "button" : undefined}
            tabIndex={onSelect ? 0 : undefined}
            aria-label={
              onSelect ? `Inspect source block ${block.id}` : undefined
            }
            onClick={onSelect ? () => onSelect(block) : undefined}
            onKeyDown={
              onSelect
                ? (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(block);
                    }
                  }
                : undefined
            }
            title={
              onSelect
                ? `${block.id} · ${block.type} · ${block.traceable ? "source mapped" : "mapping unavailable"}`
                : undefined
            }
          >
            <SourceContent block={block} />
          </div>
        ))}
      {showOverlay && (
        <div
          className="bbox-overlay"
          data-testid="bbox-overlay"
          aria-label={`Source bounding box for ${selected.id}`}
          style={regionStyle(selected)}
        >
          <span className="bbox-label">
            <Link2 size={10} />
            {selected.id}
          </span>
          <i className="bbox-corner tl" />
          <i className="bbox-corner tr" />
          <i className="bbox-corner bl" />
          <i className="bbox-corner br" />
        </div>
      )}
      <div className="paper-footer">
        <span>{reportTitle} · Fictional demonstration</span>
        <span>{String(page.page).padStart(2, "0")}</span>
      </div>
    </div>
  );
}

export function DocumentViewer({
  document,
  pageNumber,
  selected,
  onPage,
  onSelect,
  viewerRef,
}: {
  document: Document;
  pageNumber: number;
  selected: Block | null;
  onPage: (page: number) => void;
  onSelect?: (block: Block) => void;
  viewerRef?: Ref<HTMLElement>;
}) {
  const [zoom, setZoom] = useState(100);
  const [showRegions, setShowRegions] = useState(false);
  const page =
    document.pages.find((page) => page.page === pageNumber) ??
    document.pages[0];
  const showOverlay = selected?.traceable && selected.page === page.page;
  return (
    <section
      className={`source-panel panel ${showOverlay ? "source-linked" : ""}`}
      aria-label="Document source viewer"
      tabIndex={-1}
      ref={viewerRef}
    >
      <div className="viewer-heading">
        <div>
          <FileText size={16} />
          <strong>Source document</strong>
        </div>
        <span>MOCK PDF</span>
      </div>
      <div className="viewer-toolbar">
        <div className="page-controls">
          <button
            className="icon-button"
            aria-label="Previous source page"
            disabled={pageNumber === 1}
            onClick={() => onPage(pageNumber - 1)}
          >
            <ChevronLeft size={16} />
          </button>
          <span>
            Page <strong data-testid="source-page-number">{page.page}</strong>{" "}
            of {document.page_count}
          </span>
          <button
            className="icon-button"
            aria-label="Next source page"
            disabled={pageNumber === document.page_count}
            onClick={() => onPage(pageNumber + 1)}
          >
            <ChevronRight size={16} />
          </button>
        </div>
        <div className="zoom-controls">
          <button
            className={`icon-button region-toggle ${showRegions ? "active" : ""}`}
            aria-label="Show extraction regions"
            aria-pressed={showRegions}
            title="Toggle mapped extraction regions"
            onClick={() => setShowRegions(!showRegions)}
          >
            <ScanLine size={14} />
          </button>
          <button
            className="icon-button"
            aria-label="Zoom out"
            disabled={zoom === 80}
            onClick={() => setZoom((value) => value - 10)}
          >
            <Minus size={14} />
          </button>
          <span>{zoom}%</span>
          <button
            className="icon-button"
            aria-label="Zoom in"
            disabled={zoom === 120}
            onClick={() => setZoom((value) => value + 10)}
          >
            <Plus size={14} />
          </button>
        </div>
      </div>
      <div className="document-stage">
        <div className="paper-wrap" style={{ width: `${zoom}%` }}>
          <SourcePage
            page={page}
            selected={selected}
            showRegions={showRegions}
            onSelect={onSelect}
          />
        </div>
      </div>
      <div className="source-page-strip">
        {document.pages.map((item) => (
          <button
            key={item.page}
            className={item.page === pageNumber ? "active" : ""}
            aria-label={`Go to source page ${item.page}`}
            aria-pressed={item.page === pageNumber}
            onClick={() => onPage(item.page)}
          >
            <FileText size={12} />
            {String(item.page).padStart(2, "0")}
          </button>
        ))}
        <span>{document.filename}</span>
      </div>
      <div className="viewer-footer">
        <span className={showOverlay ? "cyan-dot" : "neutral-dot"} />
        {showOverlay
          ? `Source linked · ${selected.id}`
          : selected && !selected.traceable
            ? "Source mapping unavailable for this block"
            : "Select an extracted block to trace it to its source."}
        <span className="coordinate-label">NORMALIZED COORDINATES</span>
      </div>
    </section>
  );
}
