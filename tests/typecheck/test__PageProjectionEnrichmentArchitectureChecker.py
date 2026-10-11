from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from typecheck.page_projection_enrichment import scan_actual_slice, scan_paths

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).with_name("fixtures") / "page_projection_enrichment"
_PREFIX = "projectkoios-page-projection-enrichment"


def test__actual_slice__satisfies_local_architecture_checker() -> None:
    assert scan_actual_slice() == ()


def test__typed_nested_tuples_and_private_helpers__remain_permitted() -> None:
    assert scan_paths(paths=(_FIXTURES / "valid.py",)) == ()


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    (
        ("private_class.py", f"{_PREFIX}-private-class"),
        ("nested_class.py", f"{_PREFIX}-nested-class"),
        ("non_taxonomy_class.py", f"{_PREFIX}-non-taxonomy-class"),
        ("multi_verb_actionizer.py", f"{_PREFIX}-multi-verb-class"),
        ("multi_verb_facade.py", f"{_PREFIX}-multi-verb-class"),
    ),
)
def test__diagnostic_fixtures__are_rejected_mechanically(
    *, fixture_name: str, expected_code: str
) -> None:
    diagnostics = scan_paths(paths=(_FIXTURES / fixture_name,))

    assert expected_code in {diagnostic.code for diagnostic in diagnostics}


def test__normal_mypy_configuration__loads_local_checker() -> None:
    configuration = tomllib.loads(
        (_REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    mypy_configuration = configuration["tool"]["mypy"]

    assert mypy_configuration["plugins"] == [
        "typecheck.page_projection_enrichment"
    ]
