# Installing and configuring Tesseract

`TesseractOCRProcessor` invokes the external `tesseract` executable. Tesseract
is not a Python dependency and is not installed by this package. Install the
engine and the exact traineddata files required by the application's semantic
language mappings.

## macOS with Homebrew

Install Tesseract with its bundled English and orientation data:

```bash
brew install tesseract
```

The Homebrew formula includes only `eng` and `osd`. Install the optional
all-language data formula when additional languages or scripts are needed:

```bash
brew install tesseract-lang
```

Record stable paths for configuration and testing:

```bash
export KOIOS_TESSERACT_EXECUTABLE="$(command -v tesseract)"
export KOIOS_TESSERACT_ENG_TRAINEDDATA="$(brew --prefix)/share/tessdata/eng.traineddata"
```

Do not assume `/opt/homebrew`: Intel and custom Homebrew installations use a
different prefix.

## Debian or Ubuntu

Install the engine and the language packages needed by the application:

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

Additional language packages follow the distribution naming convention, such
as `tesseract-ocr-fra` or `tesseract-ocr-deu`. Locate the installed English
resource rather than hard-coding a versioned system directory:

```bash
export KOIOS_TESSERACT_EXECUTABLE="$(command -v tesseract)"
export KOIOS_TESSERACT_ENG_TRAINEDDATA="$(dpkg -L tesseract-ocr-eng | grep -m1 '/eng\.traineddata$')"
```

## Verify the installation

Confirm the executable, backend report, and installed resource names:

```bash
"$KOIOS_TESSERACT_EXECUTABLE" --version
"$KOIOS_TESSERACT_EXECUTABLE" --list-langs

test -x "$KOIOS_TESSERACT_EXECUTABLE"
test -f "$KOIOS_TESSERACT_ENG_TRAINEDDATA"
```

Run the optional real-engine adapter smoke test:

```bash
KOIOS_TESSERACT_EXECUTABLE="$KOIOS_TESSERACT_EXECUTABLE" \
KOIOS_TESSERACT_ENG_TRAINEDDATA="$KOIOS_TESSERACT_ENG_TRAINEDDATA" \
  .venv/bin/python -m pytest -q \
  tests/test__TesseractOCRProcessor.py \
  -k optional_real_engine_smoke
```

The remaining adapter tests use a hermetic executable double and do not require
Tesseract.

## Configure the adapter

Environment variables above are used only by the optional smoke test. Product
code passes executable and traineddata paths explicitly:

```python
import os
from pathlib import Path

from projectkoios.ingestion import (
    TesseractLanguageBinding,
    TesseractOCRProcessor,
)

processor = TesseractOCRProcessor(
    executable=Path(os.environ["KOIOS_TESSERACT_EXECUTABLE"]),
    language_bindings=(
        TesseractLanguageBinding(
            language="en",             # canonical semantic BCP 47 tag
            resource_name="eng",       # Tesseract backend resource name
            traineddata_path=Path(
                os.environ["KOIOS_TESSERACT_ENG_TRAINEDDATA"]
            ),
        ),
    ),
)

# Given an OCRRequest named request:
identity = processor.identity_for(request)
result = processor.action(request=request)
```

`request` must use the same ordered semantic languages as the configured
bindings. Add one binding per supported semantic tag; do not silently translate
or fall back to another language. Multiple semantic tags may explicitly share
the same backend resource.

The adapter hashes the bounded normalized version report, configured executable,
and exact requested traineddata bytes. Upgrading Tesseract or replacing a
resource therefore changes `OCRProcessorIdentity` and the OCR cache key.

## Selective batch publication

`koios-run-selective-ocr` consumes a versioned `SelectiveOCRPlan`. Every plan
item locks one `PdfBatchItem`, the exact SHA-256 of its validated
`extraction.json`, an explicit output directory, and a strictly ordered set of
zero-based page indices. Source, ingestion, and output roots are supplied
separately; symlink traversal and changed source or extraction evidence fail
closed.

The command is dry-run by default. Standard output is reserved for exactly one
machine-readable JSON summary; PyMuPDF diagnostics are routed to standard error.
Dry-run performs no OCR and reports whether each page would be created or
verified. Explicit `--apply` replays the native
extraction, renders only the selected full pages, and invokes the repository's
local `TesseractOCRProcessor`. Each page is independently published with mode
`0600` as a create-once `result.json`. Its `SelectiveOCRPublication` binds the
exact source and extraction hashes, selected page, and complete `OCRResult`,
making a partially completed plan
resumable without rerunning valid existing pages. Existing results are matched
to the exact rerendered request, processor/resource identity, and cache key.
Conflicting, partial, or unsafe artifacts are never overwritten.

Native block references and OCR tokens/lines remain separate evidence inside
the request/result contract. This command does not reconcile streams, compose
replacement text, mutate native extraction, call Search, create embeddings, or
publish a RAG index.

Example plan shape:

```json
{
  "schema_version": 1,
  "items": [
    {
      "source": {
        "source_id": "source:example",
        "pdf_path": "documents/example.pdf",
        "output_directory": "native/example",
        "sha256": "<64 lowercase hex characters>",
        "byte_size": 12345,
        "locator": "documents/example.pdf"
      },
      "extraction_sha256": "<64 lowercase hex characters>",
      "output_directory": "ocr/example",
      "pages": [{"page_index": 4}]
    }
  ]
}
```

## Selective reconciliation publication

`python -m scripts.ocr_reconciliation_batch` consumes a separate hash-locked
plan,
validated native extraction artifacts, and exact selective OCR publications.
It is dry-run by default. Explicit `--apply` writes private create-once
reconciliation evidence and exact replay performs no mutation.

The first plan version accepts only OCR selections without native-text
references because native reconciliation additionally requires exact layout
evidence. It never rerenders, invokes OCR, composes replacement text, or calls
Search.

A private 13-page operational pilot validated this boundary across nine
documents. Seven pages retained OCR text and six remained completed blank.
Apply created 13 private page publications and replay verified all 13 without
changing their hashes, sizes, or modification times. The results contain 112
OCR-only proposed items, no native segments or matches, and no reconciliation
warnings. Every proposal preserves its linked OCR line text and order exactly.

These results are provenance evidence, not accepted text. A read-only quality
review found 31 lines below 0.60 backend confidence and visible mathematical,
layout-order, and low-signal OCR errors. The proposals remain unaccepted and
chunk-ineligible, and broader empty-page reconciliation is deferred. This
pilot does not validate the mixed native/OCR path.

A later plan-only reassessment inventoried the fixed native corpus without
invoking OCR or reconciliation. It found 40 pages across five documents with a
nonempty native payload smaller than 40 UTF-8 bytes. Workflow 034 selected the
page with the largest such payload per affected document, breaking ties by the
lowest page index, and materialized exact create-once layout evidence for those
five pages. The retained plan has ID
`mixed-native-ocr-reconciliation-reassessment:sha256:dd5d762993579f974f65415d131262a7debfd916863ba73df22556663546c09d`
and SHA-256
`0997a9a3ec3a9390c2709929985b04c016ea2c39215a91c04c2dd62e8b596780`.

This closes evidence discovery only. The five pages have no retained OCR or
reconciliation publications, and plan version 1 still rejects native-text
references. Mixed execution therefore remains blocked until a later plan
contract binds each exact native page and layout result, followed by separate
OCR and reconciliation authorization. No replacement text, acceptance,
Search/indexing, or publication was performed.

## Operational boundary

The adapter uses a bounded, no-shell POSIX subprocess with timeout and output
capture limits, but a subprocess is not a security sandbox and native memory is
not capped. Deployments accepting untrusted images, executables, or traineddata
must provide operating-system sandboxing and resource controls.
