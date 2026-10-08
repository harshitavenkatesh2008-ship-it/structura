import { ArrowUpRight, Check, Link2 } from "lucide-react";
import type { ReactNode } from "react";
import type { Risk } from "../types/document";

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
export function RiskBadge({ risk }: { risk: Risk }) {
  return (
    <span className={`risk risk-${risk}`}>
      <span />
      {risk} risk
    </span>
  );
}
export function TraceBadge({ traceable }: { traceable: boolean }) {
  return (
    <span className={`trace-label ${traceable ? "" : "unmapped"}`}>
      <Link2 size={12} />
      {traceable ? "Traceable" : "Unmapped"}
    </span>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Stats({
  items,
}: {
  items: {
    label: string;
    value: string | number;
    note: string;
    icon: ReactNode;
  }[];
}) {
  return (
    <div className="stats">
      {items.map((item) => (
        <div className="stat" key={item.label}>
          <div className="stat-top">
            <span>{item.label}</span>
            {item.icon}
          </div>
          <div className="stat-value">{item.value}</div>
          <div className="stat-note">{item.note}</div>
        </div>
      ))}
    </div>
  );
}
export function MockNotice({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`mock-notice ${compact ? "compact" : ""}`}>
      <span className="demo-dot" />
      <span>
        <strong>Demo workspace.</strong>{" "}
        {compact
          ? "All document data is fictional."
          : "Mock data only. No files are uploaded or parsed, and no real extraction is performed."}
      </span>
    </div>
  );
}
export function ReadyBadge() {
  return (
    <Badge tone="green">
      <Check size={12} />
      TraceBack ready
    </Badge>
  );
}
export function OpenIcon() {
  return <ArrowUpRight size={16} />;
}
