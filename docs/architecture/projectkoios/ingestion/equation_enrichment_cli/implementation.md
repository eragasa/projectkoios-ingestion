# `ingestion.equation_enrichment_cli` implementation

The command imports `PyMuPdfRegionRenderer` directly from the adapter module,
constructs it with existing defaults, and injects it into
`DeterministicEquationAssembler`. Recognition, indexing, serialization, and
failure behavior remain unchanged; no reusable composition abstraction is
added.
