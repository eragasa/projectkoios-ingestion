from __future__ import annotations

from projectkoios.ingestion.identity import stable_id

EXTRACTION_CACHE_FORMAT_VERSION = "1"


def build_extraction_cache_key(
    *,
    source_id: str,
    source_blob_id: str,
    extractor_name: str,
    extractor_version: str,
    configuration_digest: str,
    contract_version: str,
    cache_format_version: str = EXTRACTION_CACHE_FORMAT_VERSION,
) -> str:
    """Build the complete deterministic identity for a raw extraction."""
    identity = {
        "source_id": source_id,
        "source_blob_id": source_blob_id,
        "extractor_name": extractor_name,
        "extractor_version": extractor_version,
        "configuration_digest": configuration_digest,
        "contract_version": contract_version,
        "cache_format_version": cache_format_version,
    }
    incomplete = tuple(
        name
        for name, value in identity.items()
        if not isinstance(value, str) or not value
    )
    if incomplete:
        raise ValueError(
            "cache identity fields must be non-empty strings: "
            + ", ".join(incomplete)
        )
    invalid_utf8: list[str] = []
    for name, value in identity.items():
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            invalid_utf8.append(name)
    if invalid_utf8:
        raise ValueError(
            "cache identity fields must be valid UTF-8: "
            + ", ".join(invalid_utf8)
        )
    return stable_id(
        "extraction-cache",
        cache_format_version,
        contract_version,
        source_id,
        source_blob_id,
        extractor_name,
        extractor_version,
        configuration_digest,
    )
