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

A private operational pilot exercised 13 pages from nine documents: seven
OCR-text pages and six completed blank pages. Apply created 13 publications and
exact replay preserved every artifact hash, size, and modification time. The
results contain 112 OCR-only proposals, zero native segments or matches, and
zero reconciliation warnings. All proposed text and order exactly match their
linked OCR lines. This verifies create-once OCR-only mechanics, not text quality
or the mixed native/OCR path. Quality review retained the proposals as
unaccepted and chunk-ineligible because low-confidence, equation, and
reading-order errors remain. Broader empty-page publication is intentionally deferred.
