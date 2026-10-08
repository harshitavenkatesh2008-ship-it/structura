import { useState } from "react";
import { SquareCode } from "lucide-react";
import type { Document } from "../types/document";
import { toMarkdown } from "../utils/document";
import { Badge, MockNotice, PageHeading } from "./UI";
import { CodeViewer, OutputActions } from "./OutputViewer";

export function MarkdownViewer({ document }: { document: Document }) {
  const content = toMarkdown(document);
  const [raw, setRaw] = useState(false);
  return (
    <div className="page-content">
      <PageHeading
        eyebrow="OUTPUT / MARKDOWN"
        title="Readable by people. Ready for tools."
        description="A clean, reading-order view of the same mock Document Graph."
        action={
          <OutputActions
            content={content}
            filename="northstar-report.md"
            type="text/markdown"
          />
        }
      />
      <div className="panel output-panel">
        <div className="viewer-heading">
          <div>
            <SquareCode size={17} />
            <strong>northstar-report.md</strong>
            <Badge>MARKDOWN</Badge>
          </div>
          <div
            className="segmented"
            role="group"
            aria-label="Markdown display mode"
          >
            <button
              className={!raw ? "active" : ""}
              onClick={() => setRaw(false)}
            >
              Preview
            </button>
            <button
              className={raw ? "active" : ""}
              onClick={() => setRaw(true)}
            >
              Source
            </button>
          </div>
        </div>
        {raw ? (
          <CodeViewer content={content} language="markdown" />
        ) : (
          <article className="markdown-preview">
            <h1>Northstar Acquisition Report</h1>
            <blockquote>
              Fictional mock document. No real extraction was performed.
            </blockquote>
            {document.pages.map((page) => (
              <section key={page.page}>
                <span className="markdown-page-label">
                  SOURCE PAGE {String(page.page).padStart(2, "0")}
                </span>
                {page.blocks
                  .filter((block) => !block.parent)
                  .map((block) =>
                    block.type === "heading" ? (
                      <h2 key={block.id}>
                        {block.content.replace("\n", " — ")}
                      </h2>
                    ) : block.type === "list" ? (
                      <ul key={block.id}>
                        {block.content.split("\n").map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : block.table ? (
                      <table key={block.id}>
                        <thead>
                          <tr>
                            {block.table.headers.map((cell) => (
                              <th key={cell}>{cell}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {block.table.rows.map((row) => (
                            <tr key={row[0]}>
                              {row.map((cell) => (
                                <td key={cell}>{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : block.type === "equation" ? (
                      <pre key={block.id}>{block.content}</pre>
                    ) : ["figure", "chart", "image"].includes(block.type) ? (
                      <blockquote key={block.id}>
                        <strong>{block.type.toUpperCase()}</strong>{" "}
                        {block.content}
                      </blockquote>
                    ) : (
                      <p key={block.id}>{block.content}</p>
                    ),
                  )}
              </section>
            ))}
          </article>
        )}
        <div className="output-footer">
          <span>Reading order preserved</span>
          <span>Derived from the mock graph</span>
        </div>
      </div>
      <MockNotice />
    </div>
  );
}
