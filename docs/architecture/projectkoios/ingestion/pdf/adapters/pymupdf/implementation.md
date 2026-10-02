# `pdf.adapters.pymupdf` implementation

`pymupdf.py` defines `PyMuPdfRegionRenderer` as a concrete
`PdfRegionRenderer`. Its constructor delegates configuration and preflight
composition to the PDF base. It does not override the public `render` template;
it implements only the protected backend hooks.

The lazy-load/open hooks import PyMuPDF on use, expose backend identity, open and
close the document, report password requirements and page count, and load page
state. For each unique selection, geometry-planning hooks:

1. read the backend CropBox and rotation metadata;
2. map the requested unrotated crop-box rectangle through page rotation;
3. intersect that requested display rectangle with `page.rect`, failing closed
   when the intersection is empty;
4. apply PyMuPDF `Rect`, `Matrix`, and integer-rectangle rules to obtain exact
   pixel dimensions and device origin; and
5. derive the pixel-to-source transform, effective source bounds, page label,
   rotation, and adapter-owned execution state.

Raster hooks select the configured PyMuPDF colorspace, call `get_pixmap` with
the same effective clip and DPI, require dimensions and device origin to match
the planned geometry, and convert the pixmap to immutable PNG bytes. The base
owns request/source validation, deduplication, all resource policy, ordering,
and `RenderedRegion` construction; the adapter does not duplicate them.

Verification includes an optional pytest integration test configured with one
content-addressed processed-reference root plus explicit OCR engine and language
resource paths. It inspects only immediate SHA directories and reads bounded
deterministic native-extraction `transcript.json` fields needed for selection,
then verifies the selected PDF and empty-page text hashes. It composes existing
bounded rendering and OCR primitives twice and compares canonical result and
aggregate digests in memory. It reads no prior OCR replay summary or OCR output,
commits no private fixture, and writes no output. This remains a downstream
usage example, not a production replay or corpus-observation API; existing
component tests provide hermetic coverage.
