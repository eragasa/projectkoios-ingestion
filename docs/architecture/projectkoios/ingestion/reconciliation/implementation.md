# OCR reconciliation implementation

`deterministic.py` owns bounded immutable reconciliation requests, results,
stream evidence, matches, warnings, configuration, and the authoritative
`DeterministicOCRReconciler` actionizer. Native and OCR streams remain exact and
separately selectable. Proposed merged items are unaccepted evidence and never
silently replace either source stream.

The package initializer is a namespace marker and re-exports nothing.
Selective create-once corpus publication is composed separately under
`projectkoios.ingestion.ocr.reconciliation.batch`.
