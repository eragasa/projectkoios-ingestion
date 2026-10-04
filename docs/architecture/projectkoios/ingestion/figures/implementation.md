# `ingestion.figures` implementation

The package exports its existing figure contracts and deterministic detector.
`FigureInspector` is the nominal inspection boundary, implemented by the
package-owned `PyMuPdfFigureInspector`. Renderer-facing modules depend on the
nominal `PageRegionRenderer`; they neither import nor instantiate
`PyMuPdfRegionRenderer`.

Figure-inspector behavior version 3 accepts an extracted image without geometry
only when all of the following are true:

- the exact page-local source object is present as an image block;
- image and optional mask bytes, hashes, and media types still match the raw PDF
  block;
- pixel dimensions and aggregate asset limits pass;
- the extracted block carries at least one linked extraction warning; and
- the raw backend geometry is itself malformed, non-finite, negative,
  unordered, non-positive-area, or outside the page cropbox.

Such an image remains extraction evidence but is omitted from geometric figure
artifacts and candidates. A missing warning, valid raw geometry paired with a
missing extracted box, content mismatch, or media mismatch still fails closed.
No rectangle is sorted, clamped, expanded, or synthesized.

Figure-detector behavior version 2 also keeps positive-area embedded artifacts
in page evidence while declining to promote artifacts below the configured
minimum embedded dimension or area. This prevents scanline-like PDF fragments
from exhausting the candidate bound without deleting their deterministic asset
evidence.

Centralizing figure inspection under the PDF adapter hierarchy is outside this
checkpoint and requires a separate ownership review.
