# `pdf.adapters.pymupdf` implementation

`pymupdf.py` defines `PyMuPdfRegionRenderer`. The optional dependency is loaded
lazily on use. The adapter reads exact source bytes, delegates request/source
checks to `PdfRegionRenderPreflight`, opens and closes the document, rejects
password-required input, and supplies page count and primitive crop-box facts
to policy.

For each first-occurrence selection, the adapter:

1. maps the requested unrotated crop-box rectangle through the page rotation;
2. intersects that requested display rectangle with `page.rect`, failing closed
   when the intersection is empty;
3. applies the backend matrix and integer-rectangle rules to that effective
   rectangle to obtain the exact width, height, and device origin;
4. derives the pixel-to-source transform and effective source bounds;
5. asks preflight policy to construct the neutral allocation plan; and
6. retains coordinate, label, rotation, and device facts only in adapter-private
   execution state.

After aggregate approval, the adapter selects the configured backend colorspace,
renders opaque pixels with the same effective clip and DPI, and requires width,
height, and device origin to equal the precomputed geometry. It then converts
the pixmap to PNG and constructs `RenderedRegion` with the existing processor,
backend, configuration, coordinate, and identity evidence. There is no adapter
copy of request or resource-limit policy.

Verification includes an optional pytest integration test configured with one
content-addressed processed-reference root plus explicit OCR engine and language
resource paths. It inspects only immediate SHA directories, reads only the
transcript fields needed for deterministic selection, and verifies the selected
PDF and empty-page text hashes. It composes existing bounded rendering and OCR
primitives twice and compares canonical result and aggregate digests in memory.
It reads no prior replay artifact, commits no private fixture, and writes no
output. This remains a downstream usage example, not a production replay or
corpus-observation API; existing component tests provide hermetic coverage.
