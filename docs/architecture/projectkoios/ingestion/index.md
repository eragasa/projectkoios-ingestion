# `projectkoios.ingestion`

This package owns source ingestion and destination-independent document
processing. It exposes stable ingestion contracts while keeping format-neutral
policy separate from optional format/backend integrations. The
[`documents`](documents/index.md) and [`transcripts`](transcripts/index.md)
packages define the nominal document, page, and block hierarchy. Shared
identity roots belong to [`base`](base/index.md). External runtime adapters
belong to [`integrations`](integrations/index.md). The backend-neutral
[`storage`](storage/index.md) boundaries publish exact extraction
decompositions and persist bounded processing checkpoints without leaking
backend query objects. Backend-neutral OCR evidence belongs to
[`ocr/contract`](ocr/contract/index.md), while deterministic native/OCR stream
comparison belongs to [`reconciliation`](reconciliation/index.md). The
[`page_projection`](page_projection/index.md) module validates owner reading
artifacts and exposes immutable citation-aligned text-only pages without
exposing equations or media. This package does not own cross-repository routing,
product policy, Search indexes, or downstream authoring.
