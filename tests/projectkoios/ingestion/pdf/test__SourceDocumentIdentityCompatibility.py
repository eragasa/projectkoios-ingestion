"""Compatibility fixtures for retained PDF source-document identities."""

from __future__ import annotations

from pathlib import Path

from projectkoios.ingestion.corpus import prepare_pdf_corpus
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

_FIXTURE_CONTENT = b"%PDF-1.7\nsource identity fixture\n"
_FIXTURE_SHA256 = (
    "0df1a5428b09e54495334de315b7d632aa42a27ea4d2deb5c498bb6813d87489"
)


def _private_document(*, owner: str, content: bytes) -> SourceDocument:
    return SourceDocument.from_bytes(
        content,
        source_id=f"private:{owner}:pages:0001-0032",
        media_type="application/pdf",
        locator=f"private://{owner}/pages-0001-0032.pdf",
    )


def test_source_document_preserves_flat_exact_byte_evidence() -> None:
    source = SourceDocument.from_bytes(
        _FIXTURE_CONTENT,
        source_id=f"pdf:sha256:{_FIXTURE_SHA256}",
        media_type="application/pdf",
        locator="library/fixture.pdf",
    )

    assert SHA256Fingerprinter.fingerprint(content=_FIXTURE_CONTENT) == (
        _FIXTURE_SHA256
    )
    assert source.blob_id == f"blob:sha256:{_FIXTURE_SHA256}"
    assert source.content_hash == _FIXTURE_SHA256
    assert source.hash_algorithm == "sha256"
    assert source.byte_length == len(_FIXTURE_CONTENT)
    assert serialize_contract(source) == (
        '{"blob_id":"blob:sha256:'
        + _FIXTURE_SHA256
        + '","byte_length":33,"content_hash":"'
        + _FIXTURE_SHA256
        + '","hash_algorithm":"sha256","locator":"library/fixture.pdf",'
        '"media_type":"application/pdf","source_id":"pdf:sha256:'
        + _FIXTURE_SHA256
        + '"}'
    )


def test_corpus_preparation_retains_managed_pdf_identity_and_locator(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "fixture.pdf").write_bytes(_FIXTURE_CONTENT)

    prepared = prepare_pdf_corpus(source_root)
    item = prepared.plans[0].items[0]

    assert item.source_id == f"pdf:sha256:{_FIXTURE_SHA256}"
    assert item.sha256 == _FIXTURE_SHA256
    assert item.byte_size == len(_FIXTURE_CONTENT)
    assert item.locator == "fixture.pdf"
    assert item.pdf_path.as_posix() == "fixture.pdf"
    assert item.output_directory.as_posix() == _FIXTURE_SHA256


def test_private_page_span_retains_historical_owner_identity() -> None:
    source = _private_document(owner="Kittel8ed", content=_FIXTURE_CONTENT)

    assert source.source_id == "private:Kittel8ed:pages:0001-0032"
    assert source.locator == "private://Kittel8ed/pages-0001-0032.pdf"
    assert source.blob_id == f"blob:sha256:{_FIXTURE_SHA256}"


def test_private_owner_identity_is_distinct_from_byte_equivalence() -> None:
    sze_ng = _private_document(owner="SzeNg3Ed", content=_FIXTURE_CONTENT)
    sze_lee = _private_document(owner="SzeLee3Ed", content=_FIXTURE_CONTENT)

    assert sze_ng.blob_id == sze_lee.blob_id
    assert sze_ng.content_hash == sze_lee.content_hash
    assert sze_ng.source_id == "private:SzeNg3Ed:pages:0001-0032"
    assert sze_lee.source_id == "private:SzeLee3Ed:pages:0001-0032"
    assert sze_ng.source_id != sze_lee.source_id


def test_changed_private_bytes_retain_owner_id_but_change_blob_identity() -> (
    None
):
    original = _private_document(owner="Kittel8ed", content=_FIXTURE_CONTENT)
    changed = _private_document(
        owner="Kittel8ed",
        content=b"%PDF-1.7\nchanged source identity fixture\n",
    )

    assert original.source_id == changed.source_id
    assert original.locator == changed.locator
    assert original.content_hash != changed.content_hash
    assert original.blob_id != changed.blob_id
    assert original.byte_length != changed.byte_length
