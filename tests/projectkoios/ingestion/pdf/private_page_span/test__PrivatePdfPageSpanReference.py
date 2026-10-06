"""Tests for historical private PDF page-span references."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace

import pytest
from projectkoios.ingestion.pdf.private_page_span.reference import (
    PrivatePdfPageSpanReference,
)
from projectkoios.ingestion.serialization import serialize_contract


@pytest.mark.parametrize(
    ("owner", "expected_source_id"),
    [
        ("Kittel8ed", "private:Kittel8ed:pages:0001-0032"),
        ("Neaman3Ed", "private:Neaman3Ed:pages:0001-0032"),
        (
            "RudanPhysicsSemiconductors",
            "private:RudanPhysicsSemiconductors:pages:0001-0032",
        ),
        ("SimonSS1Ed", "private:SimonSS1Ed:pages:0001-0032"),
        ("SzeLee3Ed", "private:SzeLee3Ed:pages:0001-0032"),
        ("SzeNg3Ed", "private:SzeNg3Ed:pages:0001-0032"),
        ("YuCardona4Ed", "private:YuCardona4Ed:pages:0001-0032"),
    ],
)
def test_reference_preserves_historical_owner_identity(
    owner: str,
    expected_source_id: str,
) -> None:
    reference = PrivatePdfPageSpanReference.create(
        owner=owner,
        first_page_number=1,
        last_page_number=32,
    )

    assert reference.source_id == expected_source_id
    assert reference.locator == f"private://{owner}/pages-0001-0032.pdf"


def test_reference_preserves_chunk_page_number_formulas() -> None:
    chunk_number = 4
    chunk_pages = 32
    source_page_count = 117
    first = (chunk_number - 1) * chunk_pages + 1
    last = min(source_page_count, first + chunk_pages - 1)

    reference = PrivatePdfPageSpanReference.create(
        owner="Kittel8ed",
        first_page_number=first,
        last_page_number=last,
    )

    assert reference.source_id == "private:Kittel8ed:pages:0097-0117"
    assert reference.locator == ("private://Kittel8ed/pages-0097-0117.pdf")


def test_reference_preserves_zero_based_half_open_source_span_formula() -> None:
    first_page_index = 32
    last_page_index_exclusive = 64

    reference = PrivatePdfPageSpanReference.create(
        owner="SzeLee3Ed",
        first_page_number=first_page_index + 1,
        last_page_number=last_page_index_exclusive,
    )

    assert reference.source_id == "private:SzeLee3Ed:pages:0033-0064"
    assert reference.locator == "private://SzeLee3Ed/pages-0033-0064.pdf"


def test_sze_ng_and_sze_lee_references_remain_distinct() -> None:
    sze_ng = PrivatePdfPageSpanReference.create(
        owner="SzeNg3Ed",
        first_page_number=1,
        last_page_number=32,
    )
    sze_lee = PrivatePdfPageSpanReference.create(
        owner="SzeLee3Ed",
        first_page_number=1,
        last_page_number=32,
    )

    assert sze_ng.source_id != sze_lee.source_id
    assert sze_ng.locator != sze_lee.locator


@pytest.mark.parametrize(
    ("owner", "first", "last"),
    [
        ("", 1, 32),
        ("Sze Lee", 1, 32),
        ("private:SzeLee3Ed", 1, 32),
        ("SzeLee3Ed", 0, 32),
        ("SzeLee3Ed", 33, 32),
        ("SzeLee3Ed", 1, 10_000),
        ("SzeLee3Ed", True, 32),
    ],
)
def test_reference_rejects_invalid_owner_or_page_span(
    owner: str,
    first: int,
    last: int,
) -> None:
    with pytest.raises(ValueError):
        PrivatePdfPageSpanReference.create(
            owner=owner,
            first_page_number=first,
            last_page_number=last,
        )


def test_reference_rejects_forged_derived_values() -> None:
    reference = PrivatePdfPageSpanReference.create(
        owner="Kittel8ed",
        first_page_number=1,
        last_page_number=32,
    )

    with pytest.raises(ValueError, match="source_id"):
        replace(reference, source_id="forged")
    with pytest.raises(ValueError, match="locator"):
        replace(reference, locator="forged")
    with pytest.raises(ValueError, match="unsupported"):
        replace(reference, contract_version="2.0")


def test_reference_is_immutable_and_serializes_as_flat_owner_metadata() -> None:
    reference = PrivatePdfPageSpanReference.create(
        owner="Kittel8ed",
        first_page_number=1,
        last_page_number=32,
    )

    with pytest.raises(FrozenInstanceError):
        reference.owner = "forged"  # type: ignore[misc]
    assert json.loads(serialize_contract(reference)) == {
        "contract_version": "1.0",
        "first_page_number": 1,
        "last_page_number": 32,
        "locator": "private://Kittel8ed/pages-0001-0032.pdf",
        "owner": "Kittel8ed",
        "source_id": "private:Kittel8ed:pages:0001-0032",
    }
