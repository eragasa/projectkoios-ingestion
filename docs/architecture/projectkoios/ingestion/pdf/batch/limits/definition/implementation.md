# `pdf.batch.limits.definition` implementation

The module defines:

- `MAX_PDF_BATCH_ITEMS = 256`; and
- `MAX_PDF_BATCH_TEXT_CHARACTERS = 4_096`.

The item-count ceiling bounds `PdfBatchPlan.items`. The text ceiling bounds
source IDs, portable PDF/output path text, and locators before those values are
retained by records or projected to JSON.

These values preserve the existing flat-module limits. They are not
configurable execution policy and do not replace the independent byte, depth,
node, string, and number limits required by `JsonParser`.
