# `ingestion.equation_batch_cli` implementation

The command imports `PyMuPdfRegionRenderer` directly from its adapter module,
constructs it with the existing default bounds, and injects it into
`DeterministicEquationCandidateDetector`. Parsing, batch ordering, persistence,
and exit behavior remain unchanged; no factory or registry is introduced.
