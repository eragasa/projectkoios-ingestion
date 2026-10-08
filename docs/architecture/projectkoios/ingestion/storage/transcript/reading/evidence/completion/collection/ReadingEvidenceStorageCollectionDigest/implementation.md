# `ReadingEvidenceStorageCollectionDigest` implementation

Frozen evidence over one non-completion logical collection. Creation sorts `(document_id, canonical_sha256)` members, enforces uniqueness and bounds, then fingerprints the canonical sequence; empty collections remain explicit.
