# `ingestion.equations` implementation

The module imports the nominal `PageRegionRenderer` base and removes its private
duck-typed renderer protocol and concrete PyMuPDF import. The deterministic
detector requires a renderer to be injected by its composition root; it has no
concrete default. Equation selection, rendered-result validation, bounds, and
identities otherwise remain unchanged.
