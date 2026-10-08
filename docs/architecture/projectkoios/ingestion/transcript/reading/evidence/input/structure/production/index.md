# Current structured-item production

This package owns the pure typed action that projects the current `StructuredTranscriptionResult` contract into bounded `ReadingStructuredItemProducerEvidenceInventory` values. It skips page anchors, preserves relative item order as contiguous per-page order, maps the closed current item vocabulary, and binds exact page-text producer lineage. It performs no I/O and is not a legacy decoder.
