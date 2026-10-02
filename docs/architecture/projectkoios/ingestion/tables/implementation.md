# `ingestion.tables` implementation

The package exports its existing table contracts and deterministic detector.
Renderer-facing modules depend on the nominal `PageRegionRenderer`; they neither
import nor instantiate `PyMuPdfRegionRenderer`. Existing rule-inspector
ownership is unchanged by this renderer correction.
