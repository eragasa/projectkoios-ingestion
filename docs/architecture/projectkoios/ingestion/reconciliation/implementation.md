# OCR reconciliation implementation

Each bounded immutable reconciliation request, result, stream evidence, match,
warning, configuration, and item class lives in its semantic ownership package
or direct role leaf. Those objects inherit the ingestion immutable-data base;
request and result objects additionally implement the Project Koios
action-family bases. `reconciler.py` owns the authoritative
`DeterministicOCRReconciler` actionizer, while class-free role leaves own bounded
derivation, validation, geometry, identity, and value helpers. Native and OCR
streams remain exact and separately selectable. Proposed merged items are
unaccepted evidence and never silently replace either source stream.

Package initializers are namespace markers and re-export nothing. Consumers
import definitions directly from their owning leaves. The reviewed hierarchy
inventory is the OCR [structural path map](../ocr/structural-path-map.md).
Selective create-once corpus publication is composed separately under
`projectkoios.ingestion.ocr.reconciliation.batch`.
