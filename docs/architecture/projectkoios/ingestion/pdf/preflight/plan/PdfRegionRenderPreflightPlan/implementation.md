# `PdfRegionRenderPreflightPlan` implementation

A frozen dataclass stores the exact `PageRegionSelection`, positive integer
width, height, channel count, their exact pixel product, and the exact
pixel/channel byte product. Post-initialization validation rejects booleans,
non-integers, non-positive dimensions or channel count, negative counts, and
inconsistent products.

The class contains no configurable ceilings and performs no coordinate
calculation. Only `PdfRegionRenderPreflight` creates approved instances during
the normal rendering path.
