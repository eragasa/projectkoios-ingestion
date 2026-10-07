# `pdf.batch.limits` implementation

The package separates fixed PDF-batch record ceilings from generic JSON parser
limits. Item and plan constructors use these limits regardless of construction
source; `PdfBatchPlanJsonContract` additionally supplies an explicit
`ingestion.json.limits.JsonLimits` value for wire parsing and serialization.

The package initializer is docstring-only and exports nothing.
