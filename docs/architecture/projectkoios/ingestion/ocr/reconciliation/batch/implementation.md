# Selective OCR reconciliation batch implementation

The batch plan binds a `PdfBatchItem`, native extraction SHA-256, safe OCR and
output directories, and ordered pages carrying exact selective OCR publication
SHA-256 values. Counts and paths are bounded before execution.

The repository-root `scripts/ocr_reconciliation_batch.py` composition command
is dry-run by default. Apply validates exact extraction and OCR evidence,
reconstructs the complete typed `OCRResult`, and invokes the authoritative
`DeterministicOCRReconciler`. Each page is independently serialized as a
private create-once reconciliation publication. Replay derives the result again
and requires exact equality without mutating the existing artifact.

The initial batch scope is intentionally restricted to empty-native-text OCR
selections. Native references require exact layout evidence and fail closed
until a later plan version explicitly binds that owner artifact. Reconciliation
proposals are unaccepted evidence and never replace native or OCR streams.
