import { FileText, Layers3, Link2, ShieldAlert } from "lucide-react";
import type { Block, Document } from "../types/document";
import { getBlocks } from "../utils/document";
import { Badge, MockNotice, PageHeading, Stats } from "./UI";

function distribution(blocks: Block[], field: "type" | "risk" | "extractor") {
  const counts = blocks.reduce<Record<string, number>>((counts, block) => {
    counts[block[field]] = (counts[block[field]] ?? 0) + 1;
    return counts;
  }, {});
  return Object.entries(counts).sort((a, b) => b[1] - a[1]);
}
function Distribution({
  title,
  subtitle,
  values,
  total,
  variant = "",
}: {
  title: string;
  subtitle: string;
  values: [string, number][];
  total: number;
  variant?: string;
}) {
  return (
    <section className={`panel distribution ${variant}`}>
      <div className="panel-heading">
        <h2>{title}</h2>
        <Badge>MOCK DATA</Badge>
      </div>
      <p>{subtitle}</p>
      <div className="distribution-bars">
        {values.map(([label, count]) => (
          <div className={`bar-row row-${label}`} key={label}>
            <div>
              <span>{label.replaceAll("_", " ")}</span>
              <strong>
                {count}
                <small> blocks</small>
              </strong>
            </div>
            <div className="bar-track">
              <span style={{ width: `${(count / total) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
      <div className="distribution-foot">
        {total} blocks in the mock Document Graph
      </div>
    </section>
  );
}
export function Analytics({ document }: { document: Document }) {
  const blocks = getBlocks(document);
  const traceable = blocks.filter((block) => block.traceable).length;
  const review = blocks.filter((block) => block.risk !== "low").length;
  return (
    <div className="page-content">
      <PageHeading
        eyebrow="INSIGHTS / ANALYTICS"
        title="A clearer picture of your document"
        description="Explore composition, source coverage, and review needs in the mock graph."
        action={<Badge tone="copper">MOCK DATA ONLY</Badge>}
      />
      <Stats
        items={[
          {
            label: "Source pages",
            value: document.pages.length,
            note: "In the sample report",
            icon: <FileText size={17} />,
          },
          {
            label: "Extracted blocks",
            value: blocks.length,
            note: "Authored demo content",
            icon: <Layers3 size={17} />,
          },
          {
            label: "Traceable blocks",
            value: `${traceable}/${blocks.length}`,
            note: "Source mapping available",
            icon: <Link2 size={17} />,
          },
          {
            label: "Review suggested",
            value: review,
            note: "Medium or high risk",
            icon: <ShieldAlert size={17} />,
          },
        ]}
      />
      <div className="analytics-grid">
        <Distribution
          title="Block composition"
          subtitle="Content types in reading order."
          values={distribution(blocks, "type")}
          total={blocks.length}
        />
        <div className="analytics-right">
          <Distribution
            title="Risk distribution"
            subtitle="Mock review labels, not confidence scores."
            values={distribution(blocks, "risk")}
            total={blocks.length}
            variant="risk-distribution"
          />
          <section className="panel coverage-panel">
            <div className="panel-heading">
              <h2>Source coverage</h2>
              <Link2 size={17} />
            </div>
            <div className="coverage-value">
              {traceable}
              <span> / {blocks.length}</span>
            </div>
            <div className="coverage-strip">
              {blocks.map((block) => (
                <span
                  className={block.traceable ? "mapped" : "not-mapped"}
                  key={block.id}
                  title={`${block.id}: ${block.traceable ? "traceable" : "unmapped"}`}
                />
              ))}
            </div>
            <p>
              1 block has an unresolved source mapping.
              <br />
              Inspect the scanned approval stamp on page 3.
            </p>
          </section>
        </div>
      </div>
      <Distribution
        title="Extractor usage"
        subtitle="Authored provenance labels. These extractors did not run in this frontend demo."
        values={distribution(blocks, "extractor")}
        total={blocks.length}
        variant="extractor-distribution"
      />
      <MockNotice />
    </div>
  );
}
