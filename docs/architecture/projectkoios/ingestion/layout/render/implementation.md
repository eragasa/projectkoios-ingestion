# Layout render evidence architecture

Status: this is the required target architecture for the unmerged layout-review
slice. Provisional dimension-only render evidence is not publication-ready.

`layout.render` identifies exact page pixels and the complete mapping between
source-page coordinates and raster coordinates. It does not own PDF rendering,
vendor inference, layout analysis, proposal acceptance, or image bytes.

## Contracts

`LayoutPixelMapping`, defined by `layout/render/mapping.py`, owns:

- source and pixel coordinate-system identifiers;
- requested source bounds;
- effective source bounds after renderer clipping and outward pixel rounding;
- the six finite coefficients of the affine pixel-to-source transform;
- the pixel-rounding convention;
- page rotation;
- image width and height; and
- a stable mapping identity over every field.

`LayoutPageRenderEvidence`, defined by `layout/render/evidence.py`, owns:

- source ID and source-blob ID;
- page index;
- the complete `LayoutPixelMapping`;
- image media type and SHA-256;
- renderer, backend, and configuration identity; and
- a stable render identity.

It intentionally does not contain `layout_result_id`. A rendered page is
independent evidence and may be compared with more than one analyzer result.
`LayoutReviewRequest` owns the relation between a render and one exact
`PageLayoutResult`.

Private image bytes remain outside repository contracts.

## Mapping convention

Pixel coordinates describe raster edges with the origin at the image's top-left.
The affine mapping follows:

```text
source_x = a * pixel_x + c * pixel_y + e
source_y = b * pixel_x + d * pixel_y + f
```

The stored tuple is `(a, b, c, d, e, f)`. The determinant must be finite and
non-zero. The first implementation accepts axis-aligned scaling and quarter-turn
rotation only. Shear and arbitrary-angle rotation are rejected rather than
silently approximated.

The mapping factory normalizes finite coordinates and negative zero before
identity construction. It transforms all four pixel-corner points and verifies
that their normalized envelope agrees with the declared effective source bounds.
Image dimensions and total pixels are checked before stable-ID serialization.

## Review binding

A full-page `LayoutReviewRequest` validates that:

- source ID, blob ID, and page index match the layout result;
- source coordinate systems match;
- mapping rotation matches the layout page rotation;
- requested source bounds equal the analyzed page bounds;
- effective bounds are consistent with renderer rounding; and
- every proposal lies within raster bounds.

A future cropped-region review must introduce a separate explicit eligibility
contract. It must not reinterpret `LayoutPageRenderEvidence` as full-page
coverage while silently omitting native blocks outside a crop.

## Source-block projection

Review geometry inverts the affine mapping and transforms all four corners of
each native source bounding box. For supported quarter-turn mappings, the
normalized corner envelope is an exact pixel-space axis-aligned box.

A mapped block outside the raster beyond the declared rounding tolerance is
classified as invalid review geometry. It is not silently clipped into a valid
coverage result. Positive proposal intersections and intersection-over-block-area
ratios are then measured in this exact pixel space.

## Relation to PDF rendering

The existing PDF `RenderedRegion` already retains effective source bounds,
pixel-to-source transform, rounding convention, rotation, dimensions, renderer
identity, and image hash. The canonical repository renderer path projects those
fields into `LayoutPageRenderEvidence`; it does not recompute a mapping from
width and height.

An isolated external renderer may produce the same backend-neutral contract,
but must freeze all equivalent geometry and resource identity. Supplying only
page and image dimensions is insufficient.

## Bounds

`layout/render/limits/definition.py` owns render-specific hard maxima. Initial
limits align with the existing raster safety policy:

```text
maximum dimension: 16,384 pixels
maximum raster area: 25,000,000 pixels
```

Shared identity, coordinate, and evidence-string bounds remain under
`layout/limits/definition.py`. All limits are enforced before image geometry or
external text enters canonical serialization and hashing.
