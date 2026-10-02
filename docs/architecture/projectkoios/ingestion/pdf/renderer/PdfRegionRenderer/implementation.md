# `PdfRegionRenderer` implementation

`PdfRegionRenderer` nominally inherits `PageRegionRenderer` and remains an
`ABC`. Its constructor accepts the established bounded PDF render parameters,
constructs one immutable `RegionRenderConfiguration`, and composes one
`PdfRegionRenderPreflight` from that same object. Its
`configuration_digest` property returns the configuration's stable digest.

Its concrete `render` template method owns this sequence:

1. bound the input iterable and validate media/source selection identity;
2. read and validate exact source bytes;
3. open the backend through a protected hook and obtain bounded page metadata;
4. deduplicate selections by first occurrence;
5. request backend geometry plans and feed their neutral dimensions into the
   single preflight policy;
6. approve all unique per-selection and aggregate allocations before any raster
   hook runs;
7. invoke raster hooks and receive immutable bytes plus neutral render evidence;
8. construct every canonical `RenderedRegion` in the base; and
9. restore requested order and duplicate object identity, closing backend state
   on every exit.

Protected abstract hooks cover only backend loading/identity, document open and
close mechanics, page metadata and geometry planning, and rasterization. Hook
inputs/outputs use neutral primitives plus adapter-owned opaque execution state;
they do not move validation, resource policy, ordering, or result construction
into the adapter. The base has no concrete backend import, coordinate/raster
calculation, pixmap operation, colorspace choice, or image encoding.
