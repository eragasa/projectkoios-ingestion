# `projectkoios.ingestion` implementation

`projectkoios.ingestion.__init__` remains an explicit reviewed public export
surface. Ownership packages below it keep namespace-only initializers and do not
become export-all facades.

Nominal document roots belong to `documents`; nominal transcript, page, and
block specializations belong to `transcripts`. Concrete clean transcript types
retain their established module while implementing that hierarchy. Shared
immutable identity records specialize `AbstractIdentity` from `ingestion.base`.
External runtime adapters, including Ollama, belong to `integrations`.

Backend-neutral PDF extraction actions belong to `pdf.extraction`; concrete
PyMuPDF extraction and rendering belong to `pdf.adapters.pymupdf`. Transcript
batch operations and composition belong to `transcript.batch`; transcript
evidence selection remains in `transcript.evidence.selection`. Reading-scale
artifact validation and typed text-only loading belong to the public
`page_projection` module; downstream consumers provide explicit artifact paths
and never discover or parse the transcript layout themselves.

Concrete adapter selection occurs only in explicit composition roots. The
existing explicit `PyMuPdfExtractor` exports from `projectkoios.ingestion` and
`projectkoios.ingestion.pdf` remain for this bounded correction; internal code
imports its defining adapter module and no new facade export is added. Any
facade removal is a later compatibility migration. Moving source modules into
these ownership packages does not otherwise authorize a public API break or a
compatibility-wrapper layer.

No slice may absorb cross-repository routing, storage ownership, rights,
citation, Search eligibility, indexing, or product policy.
