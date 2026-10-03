# `pdf.adapters.pymupdf` implementation

The target code package has namespace-only `__init__.py` and two concrete
modules:

- `extraction.py` defines `PyMuPdfExtractor` and owns raw PyMuPDF extraction,
  page metadata, native block sequence, assets, outlines, backend identity, and
  translation into neutral geometry/text action requests.
- `rendering.py` defines `PyMuPdfRegionRenderer` and implements the protected
  PyMuPDF hooks required by `PdfRegionRenderer`.

Neither module is re-exported through the local package initializer. Internal
composition roots import the defining module directly.

The extractor preserves supported text and image blocks even when backend
geometry is invalid. It links a bounded `pdf.invalid_block_geometry` warning to
the preserved block and records no bounding box. Unsupported block kinds and
empty composed text are omitted before geometry actionization. Valid geometry
is passed through unchanged.

The renderer retains existing neutral preflight and resource-bound ownership;
its adapter hooks do not duplicate request validation or aggregate policy.

Verification is hermetic by default. Real-corpus replay uses exact local source
identity only after owner tests pass, and it performs no model call.
