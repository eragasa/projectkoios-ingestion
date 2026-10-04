# OCR reconciliation implementation

Each bounded immutable reconciliation request, result, stream-evidence,
match, warning, configuration, and item class lives in its own named module.
Those objects inherit the ingestion immutable-data base; request and result
objects additionally implement the Project Koios action-family bases.
`reconciler.py` owns the authoritative `DeterministicOCRReconciler` actionizer,
while class-free private modules own bounded derivation, validation, geometry,
identity, and primitive helpers. Native and OCR streams remain exact and
separately selectable. Proposed merged items are unaccepted evidence and never
silently replace either source stream.

The package initializer is a namespace marker and re-exports nothing.
Selective create-once corpus publication is composed separately under
`projectkoios.ingestion.ocr.reconciliation.batch`.
