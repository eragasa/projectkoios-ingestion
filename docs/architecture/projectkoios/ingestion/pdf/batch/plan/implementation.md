# `pdf.batch.plan` implementation

`plan.py` defines one frozen dataclass, `PdfBatchPlan`, with fields in this
order:

1. `schema_version: int`
2. `items: tuple[PdfBatchItem, ...]`

Construction requires schema version `1`, a non-empty tuple, no more than
`MAX_PDF_BATCH_ITEMS`, and only `PdfBatchItem` values. It rejects duplicate
source IDs, PDF paths, and output directories while preserving the caller's
item order.

The schema-version field remains on the record because existing consumers and
replay bytes bind it. Interpretation of JSON keys and numeric tokens belongs to
`PdfBatchPlanJsonContract`; the plan only validates the resulting typed value.

Uniqueness checking remains private to this module. The module imports the item
record and PDF-batch limits but not generic JSON, commands, corpus behavior,
extraction, publication, or Workflow.

The plan has no generated plan ID, timestamp, metadata, acceptance status, or
execution authority. Its tuple order is meaningful input order. It is not an
Ingestion Base request because no synchronous action owns all consumers of this
portable record.
