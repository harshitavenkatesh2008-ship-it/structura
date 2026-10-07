import { useEffect, useState } from "react";
import { ArrowRight, Check, FileText, LoaderCircle } from "lucide-react";
import { Badge, PageHeading } from "./UI";

const stages = [
  "Detect & Route",
  "Extract & Assemble",
  "Validate",
  "TraceBack Ready",
];
export function Processing({
  filename,
  onOpen,
}: {
  filename: string;
  onOpen: () => void;
}) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    // A short visual simulation, not a reported processing time or latency.
    const timer = window.setInterval(
      () => setStep((value) => Math.min(value + 1, stages.length)),
      800,
    );
    return () => window.clearInterval(timer);
  }, []);
  const complete = step === stages.length;
  return (
    <div className="page-content processing-view">
      <PageHeading
        eyebrow="WORKSPACE / PROCESSING"
        title={
          complete
            ? "Your mock graph is ready"
            : "Building a source-connected view"
        }
        description="A simulated walkthrough of the document lifecycle. No extraction runs."
      />
      <section className="panel processing-panel">
        <div className="processing-file">
          <FileText size={24} />
          <div>
            <strong>{filename}</strong>
            <span>Workflow input only · sample report output</span>
          </div>
          <Badge tone="copper">SIMULATED</Badge>
        </div>
        <div
          className="progress-track"
          role="progressbar"
          aria-label="Mock processing progress"
          aria-valuenow={step}
          aria-valuemin={0}
          aria-valuemax={4}
        >
          <div style={{ width: `${(step / stages.length) * 100}%` }} />
        </div>
        <div className="processing-stages">
          {stages.map((stage, index) => (
            <div
              className={`processing-stage ${index < step ? "complete" : ""} ${index === step ? "current" : ""}`}
              key={stage}
            >
              <span>
                {index < step ? (
                  <Check size={18} />
                ) : index === step ? (
                  <LoaderCircle className="spin" size={18} />
                ) : (
                  index + 1
                )}
              </span>
              <div>
                <strong>{stage}</strong>
                <p>
                  {index < step
                    ? "Simulated stage complete"
                    : index === step
                      ? "Showing mock stage"
                      : "Waiting"}
                </p>
              </div>
            </div>
          ))}
        </div>
        {complete && (
          <div className="processing-complete">
            <p>
              Open the fictional Northstar report to inspect its blocks and
              source mappings.
            </p>
            <button className="button primary" onClick={onOpen}>
              Open document
              <ArrowRight size={16} />
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
