import { useState } from "react";
import { Check, Copy, Download } from "lucide-react";
import { downloadText } from "../utils/document";

export function OutputActions({
  content,
  filename,
  type,
}: {
  content: string;
  filename: string;
  type: string;
}) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setError("");
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Clipboard unavailable. Use Download to save the output.");
    }
  }
  return (
    <div className="output-actions">
      <button className="button secondary" onClick={copy}>
        {copied ? <Check size={15} /> : <Copy size={15} />}
        {copied ? "Copied" : "Copy"}
      </button>
      <button
        className="button primary"
        onClick={() => downloadText(content, filename, type)}
      >
        <Download size={15} />
        Download
      </button>
      {error && (
        <span className="copy-error" role="status">
          {error}
        </span>
      )}
    </div>
  );
}

export function JsonTokens({ line }: { line: string }) {
  const parts = line.split(
    /("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|\btrue\b|\bfalse\b|\bnull\b|-?\d+(?:\.\d+)?)/g,
  );
  return (
    <>
      {parts.map((part, index) => {
        const token = part.trim();
        const kind = token.startsWith('"')
          ? token.endsWith(":")
            ? "key"
            : "string"
          : /^(true|false|null)$/.test(token)
            ? "boolean"
            : /^-?\d/.test(token)
              ? "number"
              : "punctuation";
        return (
          <span className={`json-${kind}`} key={index}>
            {part}
          </span>
        );
      })}
    </>
  );
}

export function CodeViewer({
  content,
  language,
}: {
  content: string;
  language: "json" | "markdown";
}) {
  return (
    <div
      className={`code-viewer code-${language}`}
      tabIndex={0}
      aria-label={`${language} output`}
    >
      <pre>
        {content.split("\n").map((line, index) => (
          <div className="code-line" key={index}>
            <span className="line-number" aria-hidden="true">
              {index + 1}
            </span>
            <code
              className={
                language === "markdown" && line.startsWith("#")
                  ? "markdown-heading-code"
                  : language === "json" && line.includes(":")
                    ? "json-property"
                    : ""
              }
            >
              {language === "json" ? (
                <JsonTokens line={line || " "} />
              ) : (
                line || " "
              )}
            </code>
          </div>
        ))}
      </pre>
    </div>
  );
}
