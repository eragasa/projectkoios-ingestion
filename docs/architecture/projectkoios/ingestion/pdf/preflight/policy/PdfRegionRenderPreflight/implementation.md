# `PdfRegionRenderPreflight` implementation

The class holds one immutable `RegionRenderConfiguration`. Small methods form a
single mandatory sequence: bounded request preparation, exact source
validation, page and box validation, scale guard, first-occurrence selection
deduplication, per-selection plan construction, and aggregate plan validation.

The scale guard accepts only a finite positive input dimension and unit scale;
it preserves the existing conservative maximum-DPI rejection before a concrete
adapter constructs a potentially excessive matrix. Exact integer raster
dimensions then drive all remaining limits. Aggregate totals count each unique
selection once because each unique raster is allocated once.

Methods never accept backend objects and never infer backend geometry. They
raise `ValueError`/`TypeError` for malformed requests and
`PdfRegionRenderLimitError` for configured bound violations.
