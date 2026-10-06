from __future__ import annotations

import pytest
from projectkoios.ingestion.identity import canonical_json, to_json_value
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.sha256.verifier import SHA256Verifier


def test__sha256_hash__is_canonical_string_value() -> None:
    value = SHA256Hash("0" * 64)

    assert isinstance(value, str)
    assert value.value == "0" * 64


@pytest.mark.parametrize(
    "value",
    ("", "0" * 63, "0" * 65, "G" * 64, "A" * 64),
)
def test__sha256_hash__rejects_noncanonical_values(value: str) -> None:
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        SHA256Hash(value)


def test__sha256_hash__serializes_as_builtin_string() -> None:
    value = SHA256Hash("0" * 64)

    serialized = to_json_value(value)
    assert type(serialized) is str
    assert canonical_json({"sha256": value}) == (
        '{"sha256":"' + ("0" * 64) + '"}'
    )


def test__sha256_fingerprinter__calculates_exact_hash() -> None:
    assert SHA256Verifier.verify(
        content=b"abc",
        expected="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    )


def test__sha256_fingerprinter__supports_ordered_chunks() -> None:
    assert SHA256Verifier.verify(
        content=b"abc",
        expected=SHA256Fingerprinter.fingerprint_chunks(
            chunks=(b"a", b"b", b"c")
        ),
    )


def test__sha256_fingerprinter__rejects_non_bytes() -> None:
    with pytest.raises(TypeError, match="content must be bytes"):
        SHA256Fingerprinter.fingerprint(content="abc")  # type: ignore[arg-type]


def test__sha256_verifier__returns_comparison_result() -> None:
    expected = SHA256Fingerprinter.fingerprint(content=b"abc")

    assert SHA256Verifier.verify(content=b"abc", expected=expected)
    assert not SHA256Verifier.verify(content=b"abd", expected=expected)


def test__sha256_verifier__returns_false_for_malformed_expected_hash() -> None:
    assert not SHA256Verifier.verify(content=b"abc", expected="not-a-hash")
    assert not SHA256Verifier.verify(
        content=b"abc",
        expected=123,  # type: ignore[arg-type]
    )
    with pytest.raises(TypeError, match="content must be bytes"):
        SHA256Verifier.verify(
            content="abc",  # type: ignore[arg-type]
            expected="not-a-hash",
        )


def test__sha256_verifier__supports_ordered_chunks() -> None:
    expected = SHA256Fingerprinter.fingerprint(content=b"abc")

    assert SHA256Verifier.verify_chunks(chunks=(b"a", b"bc"), expected=expected)
    assert not SHA256Verifier.verify_chunks(
        chunks=(b"a", b"bc"),
        expected="not-a-hash",
    )
