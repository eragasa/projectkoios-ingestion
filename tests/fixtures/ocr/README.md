# Redistributable OCR image fixture

`synthetic-text.png` is a wholly synthetic RGB PNG spelling `KOIOS OCR 42` in
a tiny bitmap alphabet. It contains no external document, scan, typeface, or
image content. The fixture and its generation source are licensed under the
repository's [MIT license](../../../LICENSE).

Regenerate or verify the exact bytes from the repository root:

```bash
.venv/bin/python scripts/ocr_fixture.py --refresh
.venv/bin/python scripts/ocr_fixture.py --verify
```

The Tesseract adapter tests use this image with a hermetic executable double.
They therefore validate subprocess isolation, TSV interpretation, evidence,
limits, and failure behavior without requiring Tesseract on the test host. An
optional real-engine smoke test runs when both variables point to exact local
files. See the [Tesseract setup guide](../../../docs/tesseract.md) for
installation and resource-discovery commands:

```bash
KOIOS_TESSERACT_EXECUTABLE=/path/to/tesseract \
KOIOS_TESSERACT_ENG_TRAINEDDATA=/path/to/eng.traineddata \
  .venv/bin/python -m pytest -q \
  tests/test__TesseractOCRProcessor.py
```
