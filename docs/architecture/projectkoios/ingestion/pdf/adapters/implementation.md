# `projectkoios.ingestion.pdf.adapters` implementation

The target source hierarchy contains a concrete `pymupdf` package rather than a
single mixed backend module:

```text
adapters/
  __init__.py          # namespace only
  errors.py            # shared optional-adapter dependency error
  pymupdf/
    __init__.py        # namespace only
    extraction.py      # PyMuPdfExtractor
    rendering.py       # PyMuPdfRegionRenderer
```

Initializers contain no behavior, registry, factory, compatibility wrapper, or
export-all list. Composition roots import concrete implementations from their
defining modules.

Both concrete implementations use the shared typed dependency error and own
PyMuPDF loading and backend translation for their respective operation.
Backend-neutral validation,
resource policy, requests, results, and deterministic block actions remain in
`pdf.extraction`, `pdf.renderer`, and `pdf.preflight`.

The migration preserves current public behavior before removing any established
facade. A facade change requires a separate explicit review; moving internal
composition imports does not itself authorize a public API break.
