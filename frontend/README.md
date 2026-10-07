# STRUCTURA — source-first frontend redesign

A source-connected document intelligence workspace built with **React 19, TypeScript, Vite and plain CSS**. All report content and provenance are fictional mock data. The app does not upload files, parse documents, run OCR or extraction, or connect a backend.

## Focused TraceBack UX improvement — October 7, 2026

The existing Document/Structured inspection now gives the source document slightly more room while keeping the dark technical design and compact reading-order rows. TraceBack displays the actual selected result, selected block ID and status, the four-step provenance connection, clearer metadata, and a full-width coordinate section. Source and inspector share a restrained cyan selection accent; the exact source rectangle gains a short opacity entrance while preserving its normalized geometry.

**Trace Total Debt** selects `block_010`, switches to source page 2, focuses/scrolls the source viewer, clears prior block filters so the corresponding row is visible, and synchronizes the row, cyan rectangle and TraceBack. Repeated demo clicks work, and Document/Structured tab changes preserve selection without stealing focus. Reduced-motion preferences disable animation and use automatic scrolling. Empty state shows no fake rectangle, and the unmapped stamp retains its candidate/unverified disclosure and no source overlay.

All 14 existing and focused interaction tests passed. The two focused tests also passed after adding explicit cross-tab synchronization assertions. They cover demo filter clearing/focus, matching ID/page/extractor/risk/traceability/bbox, exact Total Debt row geometry before/after zoom, wider source layout, mobile reduced-motion behavior and truthful empty state. TypeScript and the final production build passed; public preview and the unchanged route manifest returned HTTP 200. Read-only review found no significant supported issues. Mock graph, types, service, export utilities, dependencies and route manifest remain unchanged. No backend, SAFE Router or deployment changes were made.

## Visual redesign

The supplied working frontend has been redesigned in place, not rebuilt. A graphite workspace, refined grouped sidebar, warm-orange actions, off-white typography and cyan source relationships replace the light dashboard presentation. Overview now centers the actual mock report, its source-highlighted Total Debt row, a dedicated TraceBack preview, a compact intelligence rail, graph-derived extraction signals and a clearly simulated activity stream.

### Attached-project restoration — October 7, 2026

The existing completed workspace has been restored in a fresh session with its pinned dependencies, and its development preview is running. A read-only review identified one ambiguous provenance label: coordinates for unmapped blocks are now explicitly marked **CANDIDATE BOX · UNVERIFIED**, with a tooltip explaining that they have no verified source mapping. The candidate coordinates remain visible in the graph; mapped bounding boxes and the unmapped-overlay safeguard are unchanged.

Current verification: TypeScript and the Vite production build passed, local/public HTML and route manifests returned HTTP 200, and `tests/provenance.spec.ts` passed its focused mapped/unmapped browser regression. No new backend, OCR, real upload processing or deployment was added. Historical verification below refers to the original redesign.

Document and Structured retain the shared selection/page state. TraceBack sits prominently above compact inspection rows and visualizes the provenance chain. Source regions also support keyboard/click selection, a mapped-region toggle and page-strip navigation. JSON keeps full export/copy and line-numbered raw output, adding real token highlighting, a collapsible tree and optional page/block inspection scopes. Markdown, upload validation, simulated processing and analytics retain their existing behavior. Copy/download always use the complete graph even when JSON is scoped.

The original mock Document Graph, types, data service and export utilities are byte-for-byte unchanged. The original light stylesheet remains in the source as an unused reference; `src/main.tsx` now loads the new `src/dark.css`, which imports the preserved source-page geometry in `src/source-page.css`. This is preview-only work: no deployment or backend functionality was added.

## Run locally

Use Node.js 22 and the pinned pnpm version:

```bash
corepack enable
corepack prepare pnpm@11.25.0 --activate
pnpm install
pnpm dev
```

Open `http://localhost:3000`. For a clean typecheck and production bundle, use `pnpm build`. Building is not deployment. For interaction checks, keep the dev server running in one terminal and run:

```bash
pnpm exec playwright install chromium
pnpm test
```

## Demo flow

The initial Overview shows the sample report, its graph counts and status. Click **Open document**, then select **Total Debt — $425M** in Structured output. Alternatively, use **Trace Total Debt** in the document toolbar or **Try TraceBack** on Overview.

The source changes to page 2, the output block becomes selected and the viewer highlights the exact Total Debt row. TraceBack shows `block_010`, its table type, source page, bounding box, mock `table_engine` provenance, low risk label, traceability and parent/child relationships.

Upload supports local file selection and drag/drop. Start Parsing only simulates the four stages: Detect & Route → Extract & Assemble → Validate → TraceBack Ready. The completion action opens the **same sample Northstar report**, not the uploaded document. This limitation is explicit in the UI; the filename of the sample is never replaced with the selected file's name.

## How TraceBack works

`App.tsx` holds the selected block ID and source page. Both inspection routes use the same selected state. A block selection updates both values. `DocumentViewer` reads the selected block's normalized `[x0, y0, x1, y1]` rectangle and sets:

```text
left   = x0 × 100%
top    = y0 × 100%
width  = (x1 − x0) × 100%
height = (y1 − y0) × 100%
```

The overlay and source content share the exact page surface, so the source mapping stays aligned across responsive sizes and zoom. `block_010` is on page 2 with bbox `[0.10, 0.60, 0.90, 0.65]`, the last fifth of parent table `block_009` at `[0.10, 0.40, 0.90, 0.65]`. Selecting the parent highlights the full table; selecting its child highlights only the total row. Page controls clear an out-of-page selection so provenance cannot imply a box is visible when it is not.

The scanned approval stamp on page 3 is deliberately **unmapped**. Its candidate bbox remains in the graph, but no overlay is shown and TraceBack explicitly says the source mapping is unavailable. Risk/extractor labels are authored demo metadata, not confidence scores or algorithms that ran.

## Source structure

| File / directory                                                          | Responsibility                                                          |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `src/App.tsx`                                                             | Route state, document adapter loading, shared selection and page state  |
| `src/main.tsx`, `src/dark.css`, `src/source-page.css`                      | React entry, self-hosted fonts, redesigned responsive CSS and preserved source geometry |
| `src/types/document.ts`                                                   | Document, Page, Block, BoundingBox, Risk, Extractor, BlockType and View |
| `src/data/mockDocument.ts`                                                | Fictional three-page graph with all eight block types                   |
| `src/services/documentService.ts`                                         | Mock-only replaceable frontend data interface                           |
| `src/utils/document.ts`                                                   | Reading-order flattening, Markdown serialization, text downloads        |
| `src/components/Sidebar.tsx`                                              | Responsive main navigation                                              |
| `src/components/Overview.tsx`                                             | Dashboard, graph statistics, sample report, TraceBack entry             |
| `src/components/Upload.tsx`, `Processing.tsx`                             | Local file state and simulated workflow                                 |
| `src/components/DocumentViewer.tsx`                                       | Styled source pages, page controls, zoom, bbox overlay                  |
| `src/components/StructuredBlocks.tsx`                                     | Reading-order selection, search and type filtering                      |
| `src/components/TraceBackPanel.tsx`                                       | Source provenance, relationships and unmapped state                     |
| `src/components/JSONViewer.tsx`, `MarkdownViewer.tsx`, `OutputViewer.tsx` | Formatted/readable output, copy and downloads                           |
| `src/components/Analytics.tsx`, `UI.tsx`                                  | Graph-derived counts/distributions and shared UI                        |
| `public/logo.svg`, `public/manus-routes.json`                             | Original brand mark and route manifest                                  |
| `tests/frontend.spec.ts`, `tests/redesign.spec.ts`, `playwright.config.ts` | Original regression coverage plus new redesign interaction checks       |
| `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`                   | Reproducible dependency setup                                           |
| `tsconfig.json`, `vite.config.ts`, `src/vite-env.d.ts`, `index.html`      | TypeScript/Vite application configuration                               |
| `plan.md`, `TODO.md`                                                      | Approved implementation decisions and completion criteria               |

## Mock graph

The graph contains **3 pages and 18 blocks**, across heading, paragraph, list, table, figure, chart, equation and image. Each block has an ID, page, normalized bbox, content, extractor, risk, flags, traceable status, parent and children. A small optional table field supplies headers and rows without removing any required fields. Metrics are computed from authored blocks: **17 traceable**, **5 medium/high-risk review blocks**. These counts describe the mock graph only, not extraction performance.

The debt table contains Term Loan A **$100M**, Term Loan B **$200M**, Notes **$125M**, and Total Debt **$425M**. JSON exposes the full graph and Markdown serializes the same blocks in reading order, avoiding duplicate child rows. Analytics computes content, risk, extractor and source-coverage counts directly from this graph. There are no accuracy, benchmark, latency or cost numbers.

## Future API connection

Replace `documentService.getDocument()` with an API adapter returning `Document` (or a promise of it). `App` already resolves either form. Real upload handling and processing events are intentionally not implemented; connect those later according to the backend's real contract. The existing source pages are styled mock HTML, not a PDF renderer. Production authentication, persistence and extraction are out of scope.

Navigation uses hash routes to keep the first frontend simple and preview-safe. Browser back and refresh work. The selected block and local upload are in-memory state and reset on refresh.

## Verification completed

The Vite development server runs on `0.0.0.0:3000`; local and public preview return HTTP 200. The route manifest contains the preserved root plus eight hash routes. TypeScript passes. The original six functional scenarios and four additional redesign scenarios passed. After read-only review corrections, four affected-path checks passed, including a new accessibility and tablet-metadata scenario. The exact Total Debt source overlay still matches its table row within 2 CSS pixels.

Coverage includes all navigation routes, browser back/refresh, search/type filters, local upload validation and all simulated processing stages, JSON/Markdown downloads, Total Debt/parent selection, selection clearing, unmapped stamp safeguards, source keyboard selection, region visibility, JSON tree/scope/full-graph clipboard copy, workspace disclosures, and all eight routes at phone/tablet widths without horizontal overflow. Desktop and mobile source/TraceBack layouts were visually inspected.

The existing test selectors changed only for the requested workspace heading, Documents navigation label, and an exact parent-link match now that block IDs are also visible in inspection rows. No original functional assertion was removed.

**No deployment, GitHub connection, real backend integration, file upload, OCR or extraction was performed.** The running link is a development preview.

A read-only implementation review identified tablet metadata visibility, off-canvas keyboard accessibility and JSON mode semantics; these were corrected and verified. The public-preview desktop TraceBack and mobile navigation checks also passed.

The final `pnpm build` passed with all review fixes included. The mock graph, types, service, export utilities, package manifest and lockfile remain byte-for-byte identical to the supplied project.
