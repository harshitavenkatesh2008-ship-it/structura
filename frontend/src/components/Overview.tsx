import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Crosshair,
  FileText,
  Layers3,
  Link2,
  Plus,
  ScanLine,
} from "lucide-react";
import type { Document, View } from "../types/document";
import { DEMO_DEBT_ID, reportTitle } from "../data/mockDocument";
import { getBlocks } from "../utils/document";
import { Badge, MockNotice, ReadyBadge } from "./UI";
import { SourcePage } from "./DocumentViewer";

function SignalGroup({
  title,
  values,
  total,
  variant = "",
}: {
  title: string;
  values: [string, number][];
  total: number;
  variant?: string;
}) {
  return (
    <div className={`signal-group ${variant}`}>
      <h3>{title}</h3>
      {values.map(([label, count]) => (
        <div className={`signal-row signal-${label}`} key={label}>
          <span title={label}>{label.replaceAll("_", " ")}</span>
          <div className="signal-track">
            <i style={{ width: `${(count / total) * 100}%` }} />
          </div>
          <code>{count}</code>
        </div>
      ))}
    </div>
  );
}

export function Overview({
  document,
  navigate,
  onTrace,
}: {
  document: Document;
  navigate: (view: View) => void;
  onTrace: (id: string) => void;
}) {
  const blocks = getBlocks(document);
  const debt = blocks.find((block) => block.id === DEMO_DEBT_ID)!;
  const sourcePage = document.pages.find((page) => page.page === debt.page)!;
  const counts = (field: "type" | "risk" | "extractor") =>
    Object.entries(
      blocks.reduce<Record<string, number>>((result, block) => {
        result[block[field]] = (result[block[field]] ?? 0) + 1;
        return result;
      }, {}),
    );
  const types = counts("type");
  const traceable = blocks.filter((block) => block.traceable).length;
  const activity = [
    ["Document loaded", document.filename],
    [
      "Structure detected",
      `${document.page_count} source pages · ${types.length} content types`,
    ],
    [`${blocks.length} blocks assembled`, "Reading order preserved"],
    [
      `${traceable} blocks traceable`,
      `${blocks.length - traceable} source mapping to review`,
    ],
    ["TraceBack ready", "Source-connected graph available"],
  ];
  return (
    <div className="overview page-content">
      <div className="command-heading">
        <div>
          <div className="workspace-status">
            <span className="demo-dot" /> MOCK DATA{" "}
            <span className="status-slash">/</span>
            <span className="ready-status">
              <span className="small-status" /> TRACEBACK READY
            </span>
          </div>
          <h1>Document Intelligence Workspace</h1>
          <p>
            Inspect every extracted element.{" "}
            <span>Trace every result back to its source.</span>
          </p>
        </div>
        <button className="button primary" onClick={() => navigate("upload")}>
          <Plus size={16} />
          Upload document
        </button>
      </div>
      <section
        className="document-command panel"
        aria-label="Current document intelligence"
      >
        <div className="command-section-heading">
          <div>
            <span className="section-index">01</span>
            <h2>Current document</h2>
            <Badge>PDF</Badge>
          </div>
          <button onClick={() => navigate("document")}>
            Open workspace
            <ArrowUpRight size={14} />
          </button>
        </div>
        <div className="document-command-body">
          <button
            className="report-preview-stage"
            onClick={() => onTrace(DEMO_DEBT_ID)}
            aria-label="Trace the Total Debt source region"
          >
            <div className="preview-page-marker">
              <ScanLine size={13} />
              <span>SOURCE PAGE {String(debt.page).padStart(2, "0")}</span>
              <span className="preview-live-dot" />
            </div>
            <div className="preview-paper-wrap">
              <SourcePage page={sourcePage} selected={debt} showRegions />
            </div>
            <span className="preview-caption">
              <Crosshair size={12} /> Exact location. Not just a reference.
            </span>
          </button>
          <div className="document-command-info">
            <div className="document-info-top">
              <span className="eyebrow">ACTIVE DOCUMENT</span>
              <ReadyBadge />
            </div>
            <h2>{reportTitle}</h2>
            <p className="document-filename">
              <FileText size={12} />
              {document.filename}
            </p>
            <div className="document-tags">
              <span>{document.page_count} pages</span>
              <span>{blocks.length} blocks</span>
              <span>Financial report</span>
            </div>
            <div className="trace-hero">
              <div className="trace-hero-heading">
                <span>
                  <Crosshair size={15} />
                  TraceBack
                </span>
                <span className="source-verified">
                  <Check size={11} />
                  Source verified
                </span>
              </div>
              <span className="eyebrow">EXTRACTED RESULT</span>
              <div className="debt-result">
                <strong>{debt.content.split(" — ")[0]}</strong>
                <strong>{debt.content.split(" — ")[1]}</strong>
              </div>
              <div className="trace-hero-meta">
                <code>{debt.id}</code>
                <span>Page {debt.page}</span>
                <code>{debt.extractor}</code>
              </div>
              <div className="mini-provenance-chain">
                <span>
                  <Layers3 size={12} />
                  Document Graph
                </span>
                <ArrowRight size={13} />
                <span>
                  <ScanLine size={12} />
                  Source region
                </span>
              </div>
            </div>
            <div className="document-primary-actions">
              <button
                className="button primary"
                onClick={() => navigate("document")}
              >
                Open document
                <ArrowUpRight size={15} />
              </button>
              <button
                className="button trace-action"
                onClick={() => onTrace(DEMO_DEBT_ID)}
              >
                Try TraceBack
                <ArrowRight size={15} />
              </button>
            </div>
          </div>
        </div>
        <div className="intelligence-rail" aria-label="Intelligence summary">
          <div className="intelligence-metric">
            <div>
              <strong>{blocks.length}</strong>
              <Layers3 size={16} />
            </div>
            <span>STRUCTURED BLOCKS</span>
            <div className="micro-bars">
              {document.pages.map((page) => (
                <i
                  key={page.page}
                  style={{ height: `${page.blocks.length * 2}px` }}
                  title={`Page ${page.page}: ${page.blocks.length} blocks`}
                />
              ))}
              <small>Reading-order graph</small>
            </div>
          </div>
          <div className="intelligence-metric">
            <div>
              <strong>
                {traceable}
                <em>/{blocks.length}</em>
              </strong>
              <Link2 size={16} />
            </div>
            <span>TRACEABLE</span>
            <div className="metric-coverage">
              {blocks.map((block) => (
                <i
                  key={block.id}
                  className={block.traceable ? "mapped" : "unmapped"}
                  title={`${block.id}: ${block.traceable ? "traceable" : "unmapped"}`}
                />
              ))}
            </div>
          </div>
          <div className="intelligence-metric">
            <div>
              <strong>{String(document.page_count).padStart(2, "0")}</strong>
              <FileText size={16} />
            </div>
            <span>SOURCE PAGES</span>
            <div className="micro-pages">
              {document.pages.map((page) => (
                <span key={page.page}>0{page.page}</span>
              ))}
              <small>Source connected</small>
            </div>
          </div>
          <div className="intelligence-metric">
            <div>
              <strong>{String(types.length).padStart(2, "0")}</strong>
              <ScanLine size={16} />
            </div>
            <span>CONTENT TYPES</span>
            <div className="type-dots">
              {types.map(([type]) => (
                <i key={type} title={type} />
              ))}
              <small>Beyond plain text</small>
            </div>
          </div>
        </div>
      </section>
      <div className="command-bottom">
        <section className="extraction-signals panel">
          <div className="command-section-heading">
            <div>
              <span className="section-index">02</span>
              <h2>Extraction signals</h2>
            </div>
            <button onClick={() => navigate("analytics")}>
              View analytics
              <ArrowUpRight size={14} />
            </button>
          </div>
          <div className="signals-content">
            <SignalGroup
              title="BLOCK TYPES"
              values={types}
              total={blocks.length}
            />
            <SignalGroup
              title="RISK"
              values={counts("risk")}
              total={blocks.length}
              variant="risk-signals"
            />
            <SignalGroup
              title="EXTRACTORS"
              values={counts("extractor")}
              total={blocks.length}
              variant="extractor-signals"
            />
          </div>
          <div className="signals-foot">
            <span>Derived from the current Document Graph</span>
            <button onClick={() => navigate("json")}>
              <Layers3 size={12} />
              Inspect graph
              <ArrowRight size={12} />
            </button>
          </div>
        </section>
        <section className="activity-panel panel">
          <div className="command-section-heading">
            <div>
              <span className="section-index">03</span>
              <h2>Recent activity</h2>
            </div>
            <Badge>SIMULATED</Badge>
          </div>
          <ol className="activity-timeline">
            {activity.map(([title, detail], index) => (
              <li key={title}>
                <span
                  className={`activity-node ${index === activity.length - 1 ? "activity-ready" : ""}`}
                >
                  <Check size={10} />
                </span>
                <div>
                  <strong>{title}</strong>
                  <p title={detail}>{detail}</p>
                </div>
                {index === activity.length - 1 && (
                  <span className="small-status" />
                )}
              </li>
            ))}
          </ol>
        </section>
      </div>
      <MockNotice />
    </div>
  );
}
