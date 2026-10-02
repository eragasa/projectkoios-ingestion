# `ingestion.equation_enrichment` implementation

The module depends on the nominal `PageRegionRenderer` base and removes its
concrete PyMuPDF import. `DeterministicEquationAssembler` requires an injected
renderer and has no concrete default. Assembly grouping, sanitization, bounds,
and evidence identities remain unchanged.
