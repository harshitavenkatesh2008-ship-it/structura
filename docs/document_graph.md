# Structura Document Graph v1.0

The Document Graph is the common intermediate representation used by every
Structura component.

## Rule

All extractors MUST convert their results into this schema before passing
data to another Structura component.

## Document

{
  "document_id": "doc_001",
  "filename": "example.pdf",
  "format": "pdf",
  "status": "processing",
  "page_count": 1,
  "pages": [],
  "metrics": {}
}

## Page

{
  "page": 1,
  "width": 612,
  "height": 792,
  "blocks": []
}

## Block

{
  "id": "block_001",

  "type": "paragraph",

  "page": 1,

  "bbox": [0.10, 0.20, 0.90, 0.30],

  "reading_order": 1,

  "content": {
    "text": "Example extracted text"
  },

  "extractor": "native_pdf",

  "risk": {
    "score": 0.12,
    "level": "low",
    "signals": []
  },

  "confidence": null,

  "flags": [],

  "traceable": true,

  "parent": null,

  "children": []
}

## Supported Block Types

- heading
- paragraph
- list
- table
- figure
- chart
- equation
- image

## Bounding Box Convention

Bounding boxes are normalized:

[x0, y0, x1, y1]

All values must be between 0 and 1.

Origin:

(0,0) = top-left of page.

This allows the frontend to map blocks back onto documents of different
display sizes.

## Risk Levels

low
medium
high

Risk is evidence-based and MUST NOT be treated as a calibrated probability.

## Traceability

Every extracted block should retain:

- source page
- bounding box
- extractor
- block id

This enables Structura TraceBack.

## Extractor Names

Initial standardized identifiers:

- native_pdf
- ocr
- table_engine
- vision_engine
- math_engine

## Core Rule

No Structura module should silently modify the original extracted content.

Validation problems must be recorded through risk signals and flags.

Example:

{
  "flags": [
    "NUMERIC_INCONSISTENCY"
  ]
}

## Version

Document Graph: v1.0