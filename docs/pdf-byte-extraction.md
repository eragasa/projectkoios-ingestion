# Bounded PDF byte extraction and artifact construction

Applications that already staged and authorized a PDF must use the pure
byte-owned API rather than passing a path into ingestion:

```python
from projectkoios.ingestion import (
    PdfExtractionArtifactLimits,
    extract_pdf_bytes_artifacts,
)

bundle = extract_pdf_bytes_artifacts(
    staged_pdf_bytes,
    source_id="reference:example2020",
    locator="staged/example2020.pdf",
    low_text_character_threshold=40,
    expected_source_sha256=planned_sha256,
    expected_source_byte_size=planned_size,
    maximum_pages=500,
    artifact_limits=PdfExtractionArtifactLimits(),
)
```

`content` must be exact immutable `bytes`. Expected SHA-256, expected byte size,
source ID, locator, low-text threshold, and maximum pages are explicit.
Integrity is checked before opening the PDF. `PyMuPdfExtractor` reads
`document.page_count` and raises typed `PdfPageLimitError` before calling
`load_page` when the count exceeds `maximum_pages`. The page bound and low-text
threshold are both included in `PdfExtractionConfiguration.configuration_digest`
and therefore in the extraction manifest and cache key.

The call performs no filesystem writes. It returns an immutable
`PdfExtractionArtifactBundle` containing:

- the owner-built `ExtractionResult`;
- the exact `PdfExtractionConfiguration` and artifact limits;
- `raw-extraction.json`, canonical UTF-8 JSON with a final newline; and
- one `raw-pages/page-NNNN.txt` UTF-8 payload per physical page.

Each `PdfExtractionArtifactPayload` has a canonical confined POSIX relative
path, media type, immutable bytes, byte length, and SHA-256. Payload count,
raw-extraction bytes, per-page text bytes, total bytes, path length, and maximum
pages have configured or implementation hard bounds. Bundle construction
recomputes the canonical payloads from the exact result and rejects direct
construction with changed paths, bytes, hashes, order, configuration, limits,
or bundle identity.

`extract_pdf_bytes(...)` exposes the same required byte/hash/size/page inputs
when only the `ExtractionResult` is needed. A cached or otherwise owner-built
result can be converted without writes:

```python
from projectkoios.ingestion import (
    PdfExtractionConfiguration,
    build_pdf_extraction_artifacts,
)

bundle = build_pdf_extraction_artifacts(
    result,
    configuration=PdfExtractionConfiguration(
        low_text_character_threshold=40,
        maximum_pages=500,
    ),
)
```

Applications remain responsible for publishing returned bytes through their
own authorized-root abstraction. They must not reconstruct owner payloads,
join untrusted paths, or ask ingestion to write into an application root.

The existing `koios-ingest-pdf` path-based CLI remains available for local
operation. It reads the path once, composes the byte-owned validation,
extraction, and artifact builder, then uses the existing exclusive publication
and rollback behavior. `--maximum-pages` defaults to
`DEFAULT_MAXIMUM_PDF_PAGES` (10,000). Applications with staged bytes should not
use this path API.
