# `pdf.batch.limits.error` implementation

`PdfBatchLimitError` is a `ValueError` subclass used when an item or plan exceeds
`MAX_PDF_BATCH_TEXT_CHARACTERS` or `MAX_PDF_BATCH_ITEMS`.

`PdfBatchPlanJsonContract` translates a generic `JsonLimitError` to this error
only when the exceeded bound is part of the PDF batch wire boundary. Structural
JSON failures remain JSON parse failures and record invariant failures retain
their existing `TypeError` or `ValueError` classification.

The error stores no rejected source text or payload.
