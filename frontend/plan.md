# STRUCTURA frontend redesign

## Scope and preservation
Redesign the supplied React 19 / TypeScript / Vite frontend in place. No application rebuild, backend changes, new backend functionality, deployment, or changes to the mock Document Graph. Preserve all hash routes, upload validation and simulated processing, downloads/copy, Markdown preview/source, block filtering, parent/child navigation, page controls, zoom, selection synchronization, exact normalized bounding boxes, and the unmapped-source safeguard. Keep current dependencies and locked versions.

## Design
- **Movement:** precision-engineered dark developer tooling, with editorial document contrast.
- **Principles:** source-first composition; compact readable information; meaningful accent hierarchy; truthful intelligence derived from the existing graph.
- **Color philosophy:** near-black canvas, graphite panels and hairline borders create calm technical depth. Off-white primary text and cool gray secondary text remain readable. Existing warm Structura orange owns actions and active navigation. Cyan owns provenance and connected source geometry; green validates, amber marks review, red signals high risk only. The source report remains warm white.
- **Layout:** fixed left navigation and command-center canvas. Overview has an asymmetric document workbench with a real report preview beside its extraction and source connection, compact metric rail, extraction signals, and activity. Inspection stays two-panel source/result, with dedicated visible TraceBack.
- **Signature elements:** corner-bracket extraction geometry; connected provenance rail; segmented block coverage; technical section numbers.
- **Interaction:** selections coherently join extracted block, page and source location. Buttons/rows give restrained feedback. Technical details carry native tooltips and accessible labels.
- **Animation:** 140–180ms hover and selection, 180ms navigation reveal, short bounding-box transitions, processing/status pulse only where meaningful. Respect reduced motion.
- **Typography:** existing self-hosted Geist Variable for headings/navigation/body; Geist Mono only for IDs, extractor names, coordinates, code and technical metadata. Large 30–36px workspace titles, medium 16–22px section titles, readable 11–13px technical labels.
- **Brand essence:** source-connected document intelligence for engineers and AI teams. Precise, trustworthy, considered.
- **Voice:** concise and inspection-oriented: “Inspect every extracted element.” and “Trace every result back to its source.”
- **Wordmark:** preserve supplied geometric Structura mark, refine uppercase logotype treatment.
- **Signature brand color:** existing warm source-orange/copper, #c65d3b, lifted to #ec8b5e for dark-surface highlights.

## Implementation
1. Replace light presentation styling with a coherent dark design system while retaining source normalized-coordinate mechanics.
2. Refine Sidebar groups, truthful backend/mock status and frontend-only workspace/profile disclosures.
3. Recompose Overview using the existing report's page-2 content, actual graph-derived metrics/distributions, TraceBack demo and clearly simulated activity.
4. Preserve App routing/document state. Enhance existing inspection with compact rows, source emphasis and a provenance chain; never verify the unmapped stamp.
5. Enhance JSON with token highlighting, collapsible graph tree, existing raw JSON and copy/download, plus page navigation. Retain Markdown and graph-derived analytics.
6. Run existing regressions with selectors adjusted only for intentional copy changes; add focused redesign interactions. Typecheck/build, verify local/public preview and rendered design, obtain one read-only review.

## Project structure
- `src/App.tsx`: preserved routes and synchronized document/selection state.
- `src/components/`: existing visual surfaces; reusable report preview and graph tree additions.
- `src/styles.css`: design tokens, layouts, responsive rules, document geometry and interactions.
- `src/data/mockDocument.ts`, `src/types/`, `src/utils/`, `src/services/`: unchanged graph, contracts and data/export functions.
- `public/`: existing logo and complete hash-route manifest.
- `tests/`: original functional scenarios plus redesign coverage.

## Runtime and delivery
Existing Vite on `0.0.0.0:3000`; managed Preview. Build using original `pnpm build`. Checkpoint only while auto_publish is false. Do not publish/deploy. Deliver working preview and brief UX explanation, then stop.

## Attached-project restoration
Preserve the completed frontend and locked dependencies. Restore the development service in this session. For unmapped blocks, retain the graph's coordinates but explicitly label them **CANDIDATE BOX · UNVERIFIED**, with a tooltip explaining that no verified source mapping exists. Mapped blocks retain **BOUNDING BOX** and exact overlay behavior. No graph, backend or deployment changes.

## Focused Document Inspection / TraceBack improvement
Follow the supplied October 7 instructions in place. Preserve the dark technical design language, every existing page and hash route, Document/Structured tabs, compact reading-order block rows, filters, source page/zoom/title/number controls, JSON, Markdown and Analytics. Do not modify backend or SAFE Router, replace the mock graph, invent extraction data/metrics, deploy or add unrelated features.

- **Source-first layout:** both inspection tabs use a slightly wider source column and narrower inspection column. Retain the existing single-column responsive layout and exact shared normalized page geometry.
- **Selection:** keep one selected block ID and source page in `App.tsx`, synchronizing output row, source rectangle and TraceBack. Preserve the verified-only overlay safeguard and empty state with no fake rectangle.
- **Complete demo:** add a source-focus request to the existing Total Debt/Overview TraceBack actions. After the document mounts or changes, scroll the source viewer into view and focus it without stealing focus on ordinary block selections. Clear active block filters for this explicit demo so the selected Total Debt row is always visible. Use automatic movement for reduced-motion preferences.
- **Hierarchy:** expose the actual selected extracted content at the top of TraceBack, followed by the selected block ID, verified status, compact four-step provenance path, actual graph metadata and full-width bounding-box details. Increase technical metadata legibility while keeping the inspector compact. Preserve parent/child links, flags and candidate/unmapped disclosures.
- **Visual motion:** source rectangle retains the cyan thin border, subtle glow, label and exact `[x0, y0, x1, y1]` percentage conversion. Add a short opacity-only entrance and retain fast positional transitions; no looping animation or changes to source coordinates. Active source and TraceBack panels share the cyan treatment; risk colors remain reserved for authored risk.

Existing structure remains unchanged. `App.tsx` owns the explicit demo request; `DocumentViewer.tsx` handles accessible focus and source geometry; `StructuredBlocks.tsx` handles compact filtered rows and demo visibility; `TraceBackPanel.tsx` owns the selected-result hierarchy; `dark.css` owns source-first proportions, selection accents and reduced-motion-safe styling.
