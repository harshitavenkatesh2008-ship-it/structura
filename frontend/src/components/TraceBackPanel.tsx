import {
  Check,
  Crosshair,
  Link2,
  ArrowUpRight,
  ArrowDown,
  X,
} from "lucide-react";
import type { Block, Document } from "../types/document";
import { getBlocks } from "../utils/document";
import { Badge, RiskBadge } from "./UI";

export function TraceBackPanel({
  block,
  document,
  onSelect,
  onClear,
}: {
  block: Block | null;
  document: Document;
  onSelect: (block: Block) => void;
  onClear: () => void;
}) {
  const allBlocks = getBlocks(document);
  const relation = (id: string) => (
    <button
      key={id}
      className="relation-link"
      onClick={() => {
        const related = allBlocks.find((block) => block.id === id);
        if (related) onSelect(related);
      }}
    >
      {id}
      <ArrowUpRight size={12} />
    </button>
  );
  return (
    <section
      className={`traceback-panel panel ${block ? "has-selection" : ""}`}
      aria-label="TraceBack provenance"
      aria-live="polite"
    >
      <div className="traceback-heading">
        <div>
          <Crosshair size={18} />
          <strong>TraceBack</strong>
          <span className="eyebrow">PROVENANCE</span>
        </div>
        {block && (
          <button
            className="icon-button"
            onClick={onClear}
            aria-label="Clear selected block"
          >
            <X size={15} />
          </button>
        )}
      </div>
      {!block ? (
        <div className="traceback-empty">
          <div className="traceback-empty-icon">
            <Link2 size={22} />
          </div>
          <strong>Every block has a story.</strong>
          <p>Select an extracted block to trace it to its source.</p>
          <span>SOURCE PAGE · BOUNDING BOX · EXTRACTOR</span>
        </div>
      ) : (
        <div className="traceback-body">
          <div className="traceback-selected">
            <code data-testid="provenance-block-id">{block.id}</code>
            <Badge tone={block.traceable ? "cyan" : "amber"}>
              {block.traceable && <Check size={11} />}
              {block.traceable ? "Source verified" : "UNMAPPED"}
            </Badge>
          </div>
          <div className="traceback-result" data-testid="traceback-result">
            <span className="eyebrow">SELECTED EXTRACTED RESULT</span>
            <p title={block.content}>{block.content}</p>
          </div>
          <div
            className={`provenance-path ${block.traceable ? "verified" : "unverified"}`}
            aria-label="Provenance path"
          >
            {[
              "EXTRACTED RESULT",
              "DOCUMENT GRAPH",
              "SOURCE PAGE",
              block.traceable ? "BOUNDING BOX" : "MAPPING UNAVAILABLE",
            ].map((step, index) => (
              <div key={step}>
                <span className="path-node">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span>{step}</span>
                {index < 3 && <ArrowDown size={12} />}
              </div>
            ))}
          </div>
          <dl className="provenance-grid">
            <div>
              <dt>TYPE</dt>
              <dd>{block.type}</dd>
            </div>
            <div>
              <dt>SOURCE</dt>
              <dd>Page {block.page}</dd>
            </div>
            <div>
              <dt>EXTRACTOR</dt>
              <dd>
                <code>{block.extractor}</code>
              </dd>
            </div>
            <div>
              <dt>RISK LEVEL</dt>
              <dd>
                <RiskBadge risk={block.risk} />
              </dd>
            </div>
            <div>
              <dt>TRACEABLE</dt>
              <dd>
                {block.traceable
                  ? "Yes — source mapped"
                  : "No — mapping unavailable"}
              </dd>
            </div>
            <div>
              <dt>BLOCK RELATION</dt>
              <dd>{block.parent ? "Child block" : "Root block"}</dd>
            </div>
          </dl>
          <div className="bbox-details">
            <div>
              <span
                className="eyebrow"
                title={
                  block.traceable
                    ? "Normalized [x0, y0, x1, y1] coordinates measured from the top-left of the source page"
                    : "Candidate coordinates from the Document Graph; no verified source mapping exists and no overlay is shown"
                }
              >
                {block.traceable ? "BOUNDING BOX" : "CANDIDATE BOX · UNVERIFIED"}
              </span>
              <span>0–1 · TOP-LEFT ORIGIN</span>
            </div>
            <code data-testid="provenance-bbox">
              [{block.bbox.map((value) => value.toFixed(2)).join(", ")}]
            </code>
            <div className="coordinate-keys">
              <span>x₀</span>
              <span>y₀</span>
              <span>x₁</span>
              <span>y₁</span>
            </div>
          </div>
          <div className="provenance-relations">
            <div>
              <span>Parent</span>
              {block.parent ? relation(block.parent) : <span>None</span>}
            </div>
            <div>
              <span>Children</span>
              {block.children.length ? (
                block.children.map(relation)
              ) : (
                <span>None</span>
              )}
            </div>
          </div>
          {block.flags.length > 0 && (
            <div className="flags">
              <span className="eyebrow">FLAGS</span>
              {block.flags.map((flag) => (
                <code key={flag}>{flag}</code>
              ))}
            </div>
          )}
          {!block.traceable && (
            <p className="unmapped-note">
              The graph contains a candidate location, but this block has no
              verified source mapping. No bounding-box overlay is shown.
            </p>
          )}
          <div className="traceback-note">
            <Link2 size={12} />
            {block.traceable
              ? "The highlighted region is the source of this block."
              : "Review the source mapping before relying on this block."}
          </div>
        </div>
      )}
    </section>
  );
}
