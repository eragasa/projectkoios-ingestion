# `projectkoios.ingestion.pdf` implementation

The target source layout separates backend-neutral extraction semantics from
concrete PyMuPDF execution:

```text
pdf/
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
modules. For this bounded correction, the existing explicit
`PyMuPdfExtractor` exports at `projectkoios.ingestion` and
`projectkoios.ingestion.pdf` remain compatibility surfaces. No new facade
export is added; facade removal requires a later compatibility migration.

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

This migration does not add OCR, semantic reconciliation, figure descriptions,
model selection, Search eligibility, indexing, or product routing.
