import { useRef, useState } from "react";
import { ArrowRight, FileText, UploadCloud, X } from "lucide-react";
import { Badge, MockNotice, PageHeading } from "./UI";

const supported = [
  "pdf",
  "png",
  "jpg",
  "jpeg",
  "webp",
  "tif",
  "tiff",
  "xlsx",
  "xls",
  "csv",
  "pptx",
  "ppt",
];
export function Upload({ onStart }: { onStart: (file: File) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  function selectFile(candidate?: File) {
    if (!candidate) return;
    const extension = candidate.name.split(".").pop()?.toLowerCase() ?? "";
    if (!supported.includes(extension)) {
      setError("Choose a PDF, image, spreadsheet, or presentation.");
      setFile(null);
      return;
    }
    if (candidate.size === 0) {
      setError("This file is empty. Choose a different file.");
      setFile(null);
      return;
    }
    setError("");
    setFile(candidate);
  }
  return (
    <div className="page-content upload-view">
      <PageHeading
        eyebrow="WORKSPACE / UPLOAD"
        title="Bring a document into focus"
        description="Choose a file to walk through the mock ingestion workflow."
      />
      <div className="upload-panel panel">
        <div className="panel-heading">
          <h2>Upload document</h2>
          <Badge tone="copper">FRONTEND DEMO</Badge>
        </div>
        <input
          ref={input}
          id="file-upload"
          className="visually-hidden"
          type="file"
          accept={supported.map((ext) => `.${ext}`).join(",")}
          onChange={(event) => selectFile(event.target.files?.[0])}
        />
        <div
          className={`drop-zone ${dragging ? "dragging" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            selectFile(event.dataTransfer.files[0]);
          }}
        >
          <div className="upload-icon">
            <UploadCloud size={32} strokeWidth={1.5} />
          </div>
          <h3>Drop your document here</h3>
          <p>or choose a file from your computer</p>
          <button
            className="button secondary"
            onClick={() => input.current?.click()}
          >
            Browse files
          </button>
          <div className="supported-formats">
            <span>PDF</span>
            <span>IMAGES</span>
            <span>XLSX / CSV</span>
            <span>PPTX</span>
          </div>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {file && (
          <div className="selected-file">
            <FileText size={22} />
            <div>
              <strong>{file.name}</strong>
              <span>{(file.size / 1024).toFixed(1)} KB · Selected locally</span>
            </div>
            <button
              className="icon-button"
              aria-label="Remove selected file"
              onClick={() => {
                setFile(null);
                if (input.current) input.current.value = "";
              }}
            >
              <X size={17} />
            </button>
          </div>
        )}
        <div className="upload-explanation">
          <strong>Secure document processing.</strong>
          <p>
            Your document will be uploaded to the STRUCTURA processing pipeline
            and converted into a traceable Document Graph.
          </p>
        </div>
        <div className="upload-actions">
          <span>LIVE PROCESSING</span>
          <button
            className="button primary"
            disabled={!file}
            onClick={() => file && onStart(file)}
          >
            Start Parsing
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
      <MockNotice />
    </div>
  );
}
