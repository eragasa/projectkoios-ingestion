# `pdf.preflight.policy` implementation

`policy.py` defines `PdfRegionRenderPreflight` and raises the canonical
`PdfRegionRenderLimitError` imported from `pdf.renderer`. The policy is
configured by the existing immutable `RegionRenderConfiguration` and implements
one sequence of checks:

1. consume at most `max_selections + 1` values and reject overflow;
2. require a non-empty PDF request whose typed selections identify the exact
   source;
3. verify exact source byte length and SHA-256 before parsing;
4. validate page indices, finite positive page dimensions, and requested boxes
   against primitive page bounds;
5. guard raster scaling before backend matrix construction;
6. validate exact positive raster dimensions and per-selection dimension,
   pixel, and raster-byte ceilings while constructing plans; and
7. validate aggregate unique-selection pixel and raster-byte ceilings.

Selection deduplication preserves first occurrence for allocation while the
adapter restores requested order and duplicate identity in results. Channel
accounting derives once from `RegionRenderConfiguration.color_mode`. No
backend-specific fallback or parallel limit calculation is permitted.
