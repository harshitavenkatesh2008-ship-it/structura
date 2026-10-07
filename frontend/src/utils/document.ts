import type { Document } from "../types/document";

export const getBlocks = (document: Document) =>
  document.pages.flatMap((page) => page.blocks);

export function toMarkdown(document: Document): string {
  const sections = document.pages.map((page) => {
    const content = page.blocks
      .filter((block) => !block.parent)
      .map((block) => {
        if (block.type === "heading")
          return `## ${block.content.replaceAll("\n", " — ")}`;
        if (block.type === "list")
          return block.content
            .split("\n")
            .map((item) => `- ${item}`)
            .join("\n");
        if (block.table) {
          const row = (cells: string[]) => `| ${cells.join(" | ")} |`;
          return [
            row(block.table.headers),
            row(block.table.headers.map(() => "---")),
            ...block.table.rows.map(row),
          ].join("\n");
        }
        if (block.type === "equation") return `\`${block.content}\``;
        if (["figure", "chart", "image"].includes(block.type))
          return `> ${block.type.toUpperCase()}: ${block.content}`;
        return block.content;
      })
      .join("\n\n");
    return `<!-- Source: page ${page.page} -->\n\n${content}`;
  });
  return `# Northstar Acquisition Report\n\n> Fictional mock document. No real extraction was performed.\n\n${sections.join("\n\n---\n\n")}\n`;
}

export function downloadText(content: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = window.document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
