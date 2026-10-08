import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ChevronRight,
  Crosshair,
  FileText,
  Link2,
} from "lucide-react";
import type { Block, Document, View } from "./types/document";
import { DEMO_DEBT_ID, mockDocument, reportTitle } from "./data/mockDocument";
import { documentService } from "./services/documentService";
import { getBlocks } from "./utils/document";
import { Sidebar } from "./components/Sidebar";
import { Overview } from "./components/Overview";
import { Upload } from "./components/Upload";
import { Processing } from "./components/Processing";
import { DocumentViewer } from "./components/DocumentViewer";
import { StructuredBlocks } from "./components/StructuredBlocks";
import { TraceBackPanel } from "./components/TraceBackPanel";
import { JSONViewer } from "./components/JSONViewer";
import { MarkdownViewer } from "./components/MarkdownViewer";
import { Analytics } from "./components/Analytics";
import { Badge, MockNotice, ReadyBadge } from "./components/UI";

const views: View[] = [
  "overview",
  "document",
  "structured",
  "markdown",
  "json",
  "analytics",
  "upload",
  "processing",
];
function currentView(): View {
  const route = window.location.hash.replace("#/", "") as View;
  return views.includes(route) ? route : "overview";
}
const labels: Record<View, string> = {
  overview: "Overview",
  document: "Document",
  structured: "Structured",
  markdown: "Markdown",
  json: "JSON",
  analytics: "Analytics",
  upload: "Upload document",
  processing: "Processing",
};

export default function App() {
  const [view, setView] = useState<View>(currentView);
  const [document, setDocument] = useState<Document>(mockDocument);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [filename, setFilename] = useState("");
  const [traceRequest, setTraceRequest] = useState(0);
  const handledTraceRequest = useRef(0);
  const sourceViewer = useRef<HTMLElement>(null);
  const selected =
    getBlocks(document).find((block) => block.id === selectedId) ?? null;
  useEffect(() => {
    Promise.resolve(documentService.getDocument()).then(setDocument);
  }, []);
  useEffect(() => {
    const handleHash = () => {
      setView(currentView());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", handleHash);
    return () => window.removeEventListener("hashchange", handleHash);
  }, []);
  useEffect(() => {
    if (
      view !== "document" ||
      traceRequest === handledTraceRequest.current ||
      !sourceViewer.current
    ) return;
    handledTraceRequest.current = traceRequest;
    sourceViewer.current.focus({ preventScroll: true });
    sourceViewer.current.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "start",
    });
  }, [traceRequest, view]);
  const navigate = (next: View) => {
    window.location.hash = `/${next}`;
  };
  function selectBlock(block: Block) {
    setSelectedId(block.id);
    setPage(block.page);
  }
  function traceDemo(id = DEMO_DEBT_ID) {
    const block = getBlocks(document).find((block) => block.id === id);
    if (block) {
      selectBlock(block);
      setTraceRequest((request) => request + 1);
    }
    navigate("document");
  }
  function startProcessing(name: string) {
    setFilename(name);
    setSelectedId(null);
    setPage(1);
    navigate("processing");
  }
  const isWorkspace = view === "document" || view === "structured";

  return (
    <div className="app-shell">
      <Sidebar view={view} navigate={navigate} />
      <div className="main-shell">
        <header className="app-header">
          <div className="breadcrumb">
            <span>Demo workspace</span>
            <ChevronRight size={13} />
            <strong>{labels[view]}</strong>
          </div>
          <div className="header-right">
            <span className="header-demo">
              <span className="small-status" />
              Mock data
            </span>
            <span className="header-separator" />
            <div className="profile-avatar" title="Frontend demo">
              S
            </div>
          </div>
        </header>
        <main>
          {view === "overview" && (
            <Overview
              document={document}
              navigate={navigate}
              onTrace={traceDemo}
            />
          )}
          {(view === "upload" || (view === "processing" && !filename)) && (
            <Upload onStart={startProcessing} />
          )}
          {view === "processing" && filename && (
            <Processing
              key={filename}
              filename={filename}
              onOpen={() => navigate("document")}
            />
          )}
          {isWorkspace && (
            <div className={`page-content workspace-view focus-${view}`}>
              <div className="workspace-title">
                <div>
                  <div className="eyebrow">WORKSPACE / DOCUMENT INSPECTION</div>
                  <h1>{reportTitle}</h1>
                  <p>
                    <FileText size={13} />
                    {document.filename}
                    <span>·</span>
                    {document.page_count} pages<span>·</span>
                    {document.metrics.block_count} blocks
                    <Badge>MOCK DOCUMENT</Badge>
                  </p>
                </div>
                <ReadyBadge />
              </div>
              <div className="workspace-navigation">
                <div className="workspace-tabs">
                  <button
                    className={view === "document" ? "active" : ""}
                    onClick={() => navigate("document")}
                  >
                    <FileText size={15} />
                    Document
                  </button>
                  <button
                    className={view === "structured" ? "active" : ""}
                    onClick={() => navigate("structured")}
                  >
                    <Link2 size={15} />
                    Structured
                  </button>
                </div>
                <button
                  className="button text-button quick-trace"
                  onClick={() => traceDemo()}
                >
                  <Crosshair size={15} />
                  Trace Total Debt
                  <ArrowRight size={14} />
                </button>
              </div>
              <div className="workspace-hint">
                <Link2 size={14} />
                <span>
                  Select an extracted block to connect it to its source.{" "}
                  <strong>Same content. Exact location.</strong>
                </span>
              </div>
              <div className="inspection-layout">
                <DocumentViewer
                  document={document}
                  pageNumber={page}
                  selected={selected}
                  onSelect={selectBlock}
                  viewerRef={sourceViewer}
                  onPage={(next) => {
                    setPage(next);
                    if (selected?.page !== next) setSelectedId(null);
                  }}
                />
                <div className="inspection-output">
                  <TraceBackPanel
                    block={selected}
                    document={document}
                    onSelect={selectBlock}
                    onClear={() => setSelectedId(null)}
                  />
                  <StructuredBlocks
                    document={document}
                    selected={selected}
                    onSelect={selectBlock}
                    traceRequest={traceRequest}
                  />
                </div>
              </div>
              <MockNotice compact />
            </div>
          )}
          {view === "json" && <JSONViewer document={document} />}
          {view === "markdown" && <MarkdownViewer document={document} />}
          {view === "analytics" && <Analytics document={document} />}
        </main>
        <footer className="app-footer">
          <span>
            STRUCTURA <span>/</span> SOURCE-CONNECTED INTELLIGENCE
          </span>
          <span>Frontend prototype · v0.1</span>
        </footer>
      </div>
    </div>
  );
}
