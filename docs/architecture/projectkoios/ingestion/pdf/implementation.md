# `projectkoios.ingestion.pdf` implementation

The target source layout separates backend-neutral extraction semantics from
concrete PyMuPDF execution:

```text
pdf/
  batch/
    __init__.py        # namespace only
    item.py            # immutable checksummed PDF source declaration
    plan.py            # ordered bounded plan record
    json.py            # typed version-1 PDF batch JSON boundary
    limits/
      __init__.py      # namespace only
      definition.py    # item-count and text-length bounds
      error.py         # typed batch-limit failure
  extraction/
    __init__.py        # namespace only
    contracts.py       # neutral configuration and limits
    geometry.py        # typed block-geometry action
    text.py            # typed block-text action
  adapters/
    __init__.py        # namespace only
    errors.py          # shared optional-adapter dependency error
    pymupdf/
      __init__.py      # namespace only
      extraction.py    # concrete PyMuPDF extractor
      rendering.py     # concrete PyMuPDF region renderer
```

Package initializers below the two established public facades are namespace
markers, not export-all facades. Internal callers import concrete defining
modules. The new `pdf.batch` package has no facade export: moved batch records
are removed from the ingestion root and consumers use their defining leaves.
For the earlier extraction correction, the existing explicit
`PyMuPdfExtractor` exports at `projectkoios.ingestion` and
`projectkoios.ingestion.pdf` remain compatibility surfaces. No new facade
export is added; facade removal requires a later compatibility migration.

`pdf.batch` owns immutable portable source items, ordered bounded plans, and
the PDF-specific `PdfBatchPlanJsonContract`. Shared bounded JSON mechanics come
from `ingestion.json`. The batch package performs no file discovery, source
reads, extraction, publication, or Workflow lifecycle. Its version-1 serializer
bytes remain unchanged through the hierarchy migration.

`pdf.extraction` owns neutral configuration and limit contracts, immutable
requests/results, and deterministic actions over normalized backend evidence.
It does not import PyMuPDF, open documents, read backend dictionaries, render
pages, or decide which adapter to use. `PyMuPdfExtractor` structurally satisfies
the existing `SourceExtractor` abstract base; no second extractor base is added.

`pdf.adapters.pymupdf` owns core PDF extraction and rendering through PyMuPDF:
dependency loading, document/page lifecycle, raw extraction-dictionary
normalization, image bytes, outline mechanics, coordinate-system translation,
raster execution, and backend-version evidence. Existing figure and table
inspectors retain their domain ownership during this bounded correction; any
centralization of those adapters is a separate migration.
The extractor invokes the neutral geometry and text actions after converting
raw backend values into their typed bounded requests.

The Simon page-80 correction is intentionally narrow: malformed, non-finite,
negative, unordered, or non-positive-area block geometry produces an explicit
invalid-geometry result. The concrete extractor preserves the block text or
image asset and source object identity, stores no bounding box, and emits a
bounded linked warning. It never reorders coordinates or synthesizes an area.
Valid geometry and native block order remain unchanged.

## Migration sequence

1. Establish these ownership documents before moving source modules.
2. Add and verify the backend-neutral geometry and text request/result/action
   contracts under `pdf.extraction`.
3. Move concrete extraction and rendering into the
   `pdf.adapters.pymupdf` package; update composition roots to import their
   defining modules directly.
4. Keep package initializers namespace-only; preserve only separately reviewed
   established public facades.
5. Run focused contract tests, full owner validation, source/wheel build, and a
   clean-wheel import.
6. Replay Simon physical page 80 and chunk 008 before resuming any later book.
7. Resume the sequential seven-book queue only if extraction and downstream
   detection accept the missing-geometry evidence path.

## PDF batch extension sequence

The later batch-record hierarchy extension is separately bounded:

1. Review the `pdf.batch` ownership design and exact structural path map.
2. Move item, plan, and limit ownership without changing version-1 JSON bytes.
3. Update all consumers to direct defining-leaf imports and remove root exports.
4. Delete the flat `batch.py` without a compatibility facade.
5. Split plan-record tests from command-boundary tests.
6. Verify focused and full tests, documentation, distributions, clean-wheel
   imports, command smoke, and representative byte replay.

This migration does not add OCR, semantic reconciliation, figure descriptions,
model selection, Search eligibility, indexing, or product routing.
