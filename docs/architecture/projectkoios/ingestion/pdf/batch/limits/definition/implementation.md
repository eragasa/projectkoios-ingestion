# `pdf.batch.limits.definition` implementation

The module defines record bounds:

- `MAX_PDF_BATCH_ITEMS = 256`; and
- `MAX_PDF_BATCH_TEXT_CHARACTERS = 4_096`.

It also defines the version-1 wire-document configuration:

- `MAX_PDF_BATCH_JSON_BYTES = 32 * 1024 * 1024`;
- `MAX_PDF_BATCH_JSON_ITEMS = 8_192`;
- `MAX_PDF_BATCH_JSON_STRING_BYTES = 16 * 1024`;
- `MAX_PDF_BATCH_JSON_TOTAL_STRING_BYTES = 20 * 1024 * 1024`;
- `MAX_PDF_BATCH_JSON_NUMBER_CHARACTERS = 128`; and
- `MAX_PDF_BATCH_JSON_CONTAINER_DEPTH = 4`.

The item-count ceiling bounds `PdfBatchPlan.items`. The text ceiling bounds
source IDs, portable PDF/output path text, and locators before those values are
retained by records or projected to JSON.

The two record bounds preserve the existing flat-module limits. The wire
limits accept the complete 256-item boundary replay while bounding bytes and
structure before parsing. None of these values is configurable execution
policy.
