# `projectkoios.ingestion`

This package owns source ingestion and destination-independent document
processing. It exposes stable ingestion contracts while keeping format-neutral
policy separate from optional format/backend integrations. The
[`documents`](documents/index.md) and [`transcripts`](transcripts/index.md)
packages define the nominal document, page, and block hierarchy. Shared
identity roots belong to [`base`](base/index.md). Bounded JSON values,
parsing, serialization, and typed JSON document boundaries belong to
[`json`](json/index.md). Canonical SHA-256 values, fingerprinting, and
verification belong to [`sha256`](sha256/index.md). Exact backend-neutral
references to large externally managed bytes belong to
[`artifact`](artifact/index.md). External runtime adapters
belong to [`integrations`](integrations/index.md).
Deterministic layout evidence and non-authoritative failure review belong to
[`layout`](layout/index.md). Ingestion-owned evidence for reference sources
belongs to [`reference`](reference/index.md), without transferring downstream
acceptance or publication authority. The backend-neutral
[`storage`](storage/index.md) boundaries publish exact extraction
decompositions and persist bounded processing checkpoints without leaking
backend query objects. Backend-neutral OCR evidence belongs to
[`ocr`](ocr/index.md), while deterministic native/OCR stream
comparison belongs to [`reconciliation`](reconciliation/index.md). Deterministic
structured composition belongs to [`transcription`](transcription/index.md),
whose marker-only subpackages own requests, derivations, items, omissions,
results, validation records, and cache identity. Canonical rebuildable
reading-scale evidence belongs to
[`transcript.reading.evidence`](transcript/reading/evidence/index.md). Pure
citation-aligned text projection belongs to
[`page.projection`](page/projection/index.md). MongoDB schema retention is handled
only by explicit side-by-side database migration. This package does not own
cross-repository routing, product policy, Search indexes, or downstream authoring.
