# Installing and configuring Tesseract

`TesseractOcrProcessor` invokes the external `tesseract` executable. Tesseract
is not a Python dependency and is not installed by this package. Install the
engine and the exact traineddata files required by the application's semantic
language mappings. `TesseractOCRProcessor` remains only as a deprecated
compatibility name; new code must use `TesseractOcrProcessor`.

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
    OcrProcessor,
    TesseractLanguageBinding,
    TesseractOcrProcessor,
)

backend = TesseractOcrProcessor(
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
processor = OcrProcessor(backend)

# Given an OcrRequest named request:
identity = processor.identity_for(request)
result = processor.process(request)
```

`request` must use the same ordered semantic languages as the configured
bindings. Add one binding per supported semantic tag; do not silently translate
or fall back to another language. Multiple semantic tags may explicitly share
the same backend resource.

## Implementation boundary

The adapter is divided by responsibility under `ocr/processors/tesseract/`:

- `processor.py` orchestrates requests and constructs results.
- `inspection.py` verifies executable and traineddata identities and stages
  resources.
- `runner.py` owns bounded subprocess execution.
- `tsv.py` parses TSV and projects tokens and lines.
- `models.py` owns adapter configuration and internal evidence models.
- `resources.py`, `identity.py`, and `errors.py` own their respective concerns.
- `base.py` defines the Tesseract-specific model and runner contracts.

The adapter hashes the bounded normalized version report, configured executable,
and exact requested traineddata bytes. Upgrading Tesseract or replacing a
resource therefore changes `OcrProcessorIdentity` and the OCR cache key.

## Operational boundary

The adapter uses a bounded, no-shell POSIX subprocess with timeout and output
capture limits, but a subprocess is not a security sandbox and native memory is
not capped. Deployments accepting untrusted images, executables, or traineddata
must provide operating-system sandboxing and resource controls.
