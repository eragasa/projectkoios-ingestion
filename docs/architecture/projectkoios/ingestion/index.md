# `projectkoios.ingestion`

This package owns source ingestion and destination-independent document
processing. It exposes stable ingestion contracts while keeping format-neutral
policy separate from optional format/backend integrations. The
[`documents`](documents/index.md) and [`transcripts`](transcripts/index.md)
packages define the nominal document, page, and block hierarchy. Shared
identity roots belong to [`base`](base/index.md). Canonical SHA-256 values,
fingerprinting, and verification belong to [`sha256`](sha256/index.md).
External runtime adapters belong to [`integrations`](integrations/index.md).
Deterministic layout evidence and non-authoritative failure review belong to
[`layout`](layout/index.md). The backend-neutral [`storage`](storage/index.md)
boundaries publish exact extraction
decompositions and persist bounded processing checkpoints without leaking
backend query objects. Backend-neutral OCR evidence belongs to
[`ocr`](ocr/index.md), while deterministic native/OCR stream
comparison belongs to [`reconciliation`](reconciliation/index.md). Deterministic
structured composition belongs to [`transcription`](transcription/index.md),
whose marker-only subpackages own requests, derivations, items, omissions,
results, validation records, and cache identity. The
[`page_projection`](page_projection/index.md) module validates owner reading
artifacts and exposes immutable citation-aligned text-only pages without
exposing equations or media. This package does not own cross-repository routing,
product policy, Search indexes, or downstream authoring.
