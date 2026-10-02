# `ingestion.figures` implementation

The package exports its existing figure contracts and deterministic detector.
Renderer-facing modules depend on the nominal `PageRegionRenderer`; they neither
import nor instantiate `PyMuPdfRegionRenderer`. Existing inspector ownership is
unchanged by this renderer correction.
