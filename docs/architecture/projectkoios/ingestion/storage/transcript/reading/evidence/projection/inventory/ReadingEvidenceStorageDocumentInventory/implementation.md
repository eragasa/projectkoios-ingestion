# `ReadingEvidenceStorageDocumentInventory` implementation

Constructor accepts variadic concrete storage documents, enforces one scope, canonical `(collection, document_id)` ordering, uniqueness, and the configured global record ceiling. Iteration preserves canonical order.
