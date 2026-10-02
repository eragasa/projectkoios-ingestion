# projectkoios-ingestion

`projectkoios-ingestion` is the document-ingestion package for Project Koios.
It extracts content from source documents and produces structured evidence for
later analysis. Derived results retain links to the source bytes, page, and
region from which they were obtained, allowing processing steps to be reproduced
and audited.

## Scope

The repository contains:

- PDF extraction and extraction-artifact generation;
- page-layout and article-structure analysis;
- equation, table, and figure detection;
- optional OCR and equation-recognition adapters;
- structured and plain-text transcript generation;
- provenance checks for derived artifacts; and
- command-line tools for single-document and batch processing.

The package defines document-processing contracts but does not provide search
storage, vector databases, bibliography management, citation policy, rights
clearance, or publication workflows. Cross-repository responsibilities are
listed in `projectkoios/maps/repositories.md`.

## Requirements

Python 3.14 or later is required. Install the `pdf` extra to process PDF files
and the `mathml` extra to convert LaTeX output to MathML.
[Tesseract](docs/tesseract.md) for OCR, [pix2tex](docs/pix2tex.md) for equation
recognition, and [Ollama](docs/ollama-multimodal.md) for multimodal processing
are external programs or services and must be configured separately when used.

## Installation

Install the development environment with `uv`:

```bash
uv sync --extra dev
```

Available extras are:

- `pdf` for PyMuPDF support;
- `mathml` for LaTeX-to-MathML conversion; and
- `dev` for development and test dependencies.

## Command-line programs

| Program | Function |
| --- | --- |
| `koios-ingest-pdf` | Extract one PDF. |
| `koios-ingest-pdf-batch` | Extract PDFs described by a batch plan. |
| `koios-detect-pdf-equations-batch` | Detect equation candidates in an extracted batch. |
| `koios-enrich-pdf-equations-batch` | Run configured equation-recognition tools. |
| `koios-plan-pdf-transcripts-batch` | Prepare a transcript batch plan. |
| `koios-compose-pdf-transcripts-batch` | Generate transcript artifacts from a plan. |

Batch commands perform a dry run unless `--apply` is supplied. Run a command
with `--help` for its arguments and input requirements.

## Reproducibility and limitations

Source documents and derived objects are identified by content hashes and
versioned processing metadata. Operations place explicit limits on input counts,
serialized data, raster allocation, and external-process output. Existing
artifacts are checked before reuse and are not silently replaced.

These checks establish consistency of the software records; they do not show
that extracted text is correct, that OCR is adequate, or that a derived result
is scientifically valid. PyMuPDF, OCR engines, and model executables are not
security sandboxes. Processing untrusted documents may require operating-system
isolation in addition to the limits implemented here.

## Development

Run the standard checks from the repository root:

```bash
uv run ruff check .
uv run mypy src/python
uv run python -m pytest -q
uv build
```

The continuous-integration environment is described in
[`docs/ci.md`](docs/ci.md).

## Documentation

- [Architecture](docs/architecture/index.md)
- [Current ingestion architecture](docs/architecture/projectkoios/ingestion/index.md)
- [Contract catalog](docs/contracts/README.md)
- [PDF byte extraction](docs/pdf-byte-extraction.md)
- [Tesseract configuration](docs/tesseract.md)
- [Pix2tex configuration](docs/pix2tex.md)
- [Ollama multimodal processing](docs/ollama-multimodal.md)
- [Document-processing backlog](docs/tasks/document-processing-backlog.md)
- [PDF test fixtures](tests/fixtures/pdf/README.md)
- [OCR test fixture](tests/fixtures/ocr/README.md)

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
