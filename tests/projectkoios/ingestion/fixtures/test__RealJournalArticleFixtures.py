from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIRECTORY = (
    ROOT / "tests" / "fixtures" / "pdf" / "real-journal-articles"
)
MANIFEST_PATH = FIXTURE_DIRECTORY / "manifest.json"
README_PATH = FIXTURE_DIRECTORY / "README.md"

_JIANG_SHA256 = (
    "08156c7378832cd26f4daabb52af23fc474468881dce78c7c6e420ac6025630b"
)
_DICK_DAHM_SHA256 = (
    "3ab2ca08c875cb5966d580c6af631eaedec6a09a0cfca60999a20f9e7c7f0084"
)
_LICENSE_URI = "https://creativecommons.org/licenses/by/4.0/"
_CHANGE_STATEMENT = "No changes were made to the PDF bytes."
_NON_RELICENSING_STATEMENT = (
    "The repository's Apache License 2.0 applies only to Project Koios-owned "
    "code and text. It does not relicense either third-party PDF. Each PDF "
    "remains copyrighted by its stated authors and is distributed under its "
    "recorded CC BY 4.0 terms."
)
_RECORD_KEYS = (
    "relative_path",
    "sha256",
    "byte_size",
    "pdf_version",
    "physical_page_count",
    "article_page_count",
    "encrypted",
    "doi",
    "title",
    "authors",
    "journal",
    "volume",
    "article_number",
    "publication_year",
    "published_date",
    "publisher",
    "copyright",
    "source_url",
    "source_version",
    "retrieval_date",
    "license_spdx",
    "license_uri",
    "attribution",
    "exact_bytes_unmodified",
    "change_statement",
    "third_party_material_caveat",
    "rendition_note",
    "identity_status",
    "scientific_acceptance",
)
_SOURCE_EVIDENCE: dict[str, object] = {
    "owner": "projectkoios-references",
    "identity_status": "unaccepted-candidate",
    "source_id": "operatorWannierRecommendation20260917",
    "mode": "private-local-candidate-source-acquisition",
    "manifest_generated_at": "2026-09-17T19:43:11.614916+00:00",
    "manifest_sha256": (
        "1b1e8fef35b38d67e22ff02776504f863a6b143bebe6031b00db1a73783adc43"
    ),
    "acceptance_authority": False,
    "runtime_dependency": False,
}
_JIANG_RECORD: dict[str, object] = {
    "relative_path": f"{_JIANG_SHA256}.pdf",
    "sha256": _JIANG_SHA256,
    "byte_size": 2_268_128,
    "pdf_version": "PDF 1.4",
    "physical_page_count": 11,
    "article_page_count": 11,
    "encrypted": False,
    "doi": "10.1038/s41524-025-01835-8",
    "title": (
        "Robust Wannierization including magnetization and spin-orbit coupling "
        "via projectability disentanglement"
    ),
    "authors": [
        "Yuhao Jiang",
        "Junfeng Qiao",
        "Nataliya Paulish",
        "Weisheng Zhao",
        "Nicola Marzari",
        "Giovanni Pizzi",
    ],
    "journal": "npj Computational Materials",
    "volume": "11",
    "article_number": "353",
    "publication_year": 2025,
    "published_date": None,
    "publisher": "Springer Nature",
    "copyright": "© The Author(s) 2025",
    "source_url": "https://www.nature.com/articles/s41524-025-01835-8.pdf",
    "source_version": "published-version",
    "retrieval_date": "2026-09-17",
    "license_spdx": "CC-BY-4.0",
    "license_uri": _LICENSE_URI,
    "attribution": (
        "Yuhao Jiang, Junfeng Qiao, Nataliya Paulish, Weisheng Zhao, Nicola "
        'Marzari, and Giovanni Pizzi, "Robust Wannierization including '
        "magnetization and spin-orbit coupling via projectability "
        'disentanglement," npj Computational Materials 11, 353 (2025), '
        "https://doi.org/10.1038/s41524-025-01835-8."
    ),
    "exact_bytes_unmodified": True,
    "change_statement": _CHANGE_STATEMENT,
    "third_party_material_caveat": (
        "Images or other third-party material are included under the article's "
        "Creative Commons license unless a credit line indicates otherwise; "
        "uses not permitted by statutory regulation or exceeding the permitted "
        "use require permission directly from the copyright holder."
    ),
    "rendition_note": None,
    "identity_status": "unaccepted-candidate",
    "scientific_acceptance": False,
}
_DICK_DAHM_RECORD: dict[str, object] = {
    "relative_path": f"{_DICK_DAHM_SHA256}.pdf",
    "sha256": _DICK_DAHM_SHA256,
    "byte_size": 4_120_586,
    "pdf_version": "PDF 1.7",
    "physical_page_count": 13,
    "article_page_count": 12,
    "encrypted": False,
    "doi": "10.1088/2516-1075/ae1776",
    "title": "Optimization of ab-initio based tight-binding models",
    "authors": ["Henrik Dick", "Thomas Dahm"],
    "journal": "Electronic Structure",
    "volume": "7",
    "article_number": "047001",
    "publication_year": 2025,
    "published_date": "2025-11-05",
    "publisher": "IOP Publishing Ltd",
    "copyright": "© 2025 The Author(s). Published by IOP Publishing Ltd",
    "source_url": (
        "https://iopscience.iop.org/article/10.1088/2516-1075/ae1776/pdf"
    ),
    "source_version": "published-version",
    "retrieval_date": "2026-09-17",
    "license_spdx": "CC-BY-4.0",
    "license_uri": _LICENSE_URI,
    "attribution": (
        'Henrik Dick and Thomas Dahm, "Optimization of ab-initio based '
        'tight-binding models," Electronic Structure 7, 047001 (2025), '
        "https://doi.org/10.1088/2516-1075/ae1776."
    ),
    "exact_bytes_unmodified": True,
    "change_statement": _CHANGE_STATEMENT,
    "third_party_material_caveat": None,
    "rendition_note": (
        "Physical page 1 is an IOP cover/download page stating that the PDF "
        "was downloaded from IP address 138.84.137.110 on 17/09/2026 at 20:41; "
        "physical pages 2-13 are article pages numbered 1-12, and metadata "
        "records modification 2026-09-17T20:41:18+01:00."
    ),
    "identity_status": "unaccepted-candidate",
    "scientific_acceptance": False,
}
_RECORDS = [_JIANG_RECORD, _DICK_DAHM_RECORD]
_EXPECTED_MANIFEST: dict[str, object] = {
    "schema_version": 1,
    "fixture_purpose": "workflow-child-per-pdf-real-article-pilot",
    "owner": "projectkoios-ingestion",
    "source_evidence": _SOURCE_EVIDENCE,
    "records": _RECORDS,
}


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_manifest(raw: bytes) -> object:
    return json.loads(
        raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
    )


def _canonical_manifest_bytes() -> bytes:
    return (
        json.dumps(_EXPECTED_MANIFEST, ensure_ascii=True, indent=2) + "\n"
    ).encode("utf-8")


def _observe_pdf(path: Path) -> tuple[str, int, bool, tuple[str, ...]]:
    document = pymupdf.open(path)  # type: ignore[no-untyped-call]
    with document:
        metadata = document.metadata
        assert metadata is not None
        pdf_format = metadata.get("format")
        assert isinstance(pdf_format, str)
        return (
            pdf_format,
            document.page_count,
            document.is_encrypted,
            tuple(document.embfile_names()),
        )


def test__real_journal_article_fixtures__exact_directory_inventory() -> None:
    expected_names = {
        "README.md",
        "manifest.json",
        f"{_JIANG_SHA256}.pdf",
        f"{_DICK_DAHM_SHA256}.pdf",
    }
    entries = tuple(FIXTURE_DIRECTORY.iterdir())

    assert {entry.name for entry in entries} == expected_names
    assert all(entry.is_file() for entry in entries)
    assert all(not entry.is_symlink() for entry in entries)


def test__real_journal_article_fixtures__canonical_exact_manifest() -> None:
    raw = MANIFEST_PATH.read_bytes()

    assert raw == _canonical_manifest_bytes()
    assert _decode_manifest(raw) == _EXPECTED_MANIFEST
    assert tuple(_EXPECTED_MANIFEST) == (
        "schema_version",
        "fixture_purpose",
        "owner",
        "source_evidence",
        "records",
    )
    assert "manifest_sha256" not in _EXPECTED_MANIFEST
    assert tuple(_SOURCE_EVIDENCE) == (
        "owner",
        "identity_status",
        "source_id",
        "mode",
        "manifest_generated_at",
        "manifest_sha256",
        "acceptance_authority",
        "runtime_dependency",
    )


def test__real_journal_article_fixtures__provenance_and_rights() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert _NON_RELICENSING_STATEMENT in readme
    assert "No changes were made to the PDF bytes." in readme
    assert "unaccepted-candidate" in readme
    assert "manual visual rights audit" in readme
    assert "17/09/2026 at 20:41" in readme
    assert "13 physical pages" in readme
    assert "12 article pages" in readme
    for record in _RECORDS:
        assert tuple(record) == _RECORD_KEYS
        assert record["license_spdx"] == "CC-BY-4.0"
        assert record["license_uri"] == _LICENSE_URI
        assert record["retrieval_date"] == "2026-09-17"
        assert record["source_version"] == "published-version"
        assert record["change_statement"] == _CHANGE_STATEMENT
        assert record["exact_bytes_unmodified"] is True
        assert record["identity_status"] == "unaccepted-candidate"
        assert record["scientific_acceptance"] is False
        for required_value in (
            record["doi"],
            record["copyright"],
            record["source_url"],
            record["sha256"],
        ):
            assert isinstance(required_value, str)
            assert required_value in readme


def test__real_journal_article_fixtures__exact_pdf_bytes() -> None:
    for record in _RECORDS:
        relative_path = record["relative_path"]
        expected_digest = record["sha256"]
        expected_size = record["byte_size"]
        assert isinstance(relative_path, str)
        assert isinstance(expected_digest, str)
        assert isinstance(expected_size, int)
        assert relative_path == f"{expected_digest}.pdf"

        path = FIXTURE_DIRECTORY / relative_path
        payload = path.read_bytes()
        assert path.is_file()
        assert not path.is_symlink()
        assert len(payload) == expected_size
        assert hashlib.sha256(payload).hexdigest() == expected_digest
        assert payload.startswith(b"%PDF-")
        assert record["exact_bytes_unmodified"] is True


def test__real_journal_article_fixtures__bounded_pdf_structure() -> None:
    assert _observe_pdf(FIXTURE_DIRECTORY / f"{_JIANG_SHA256}.pdf") == (
        "PDF 1.4",
        11,
        False,
        (),
    )
    assert _observe_pdf(FIXTURE_DIRECTORY / f"{_DICK_DAHM_SHA256}.pdf") == (
        "PDF 1.7",
        13,
        False,
        (),
    )
    assert _DICK_DAHM_RECORD["article_page_count"] == 12
    assert "article pages numbered 1-12" in str(
        _DICK_DAHM_RECORD["rendition_note"]
    )


def test__real_article_fixtures__static_package_boundaries() -> None:
    attributes = (
        (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    )
    assert attributes[-3:] == [
        "tests/fixtures/pdf/real-journal-articles/*.pdf binary",
        "tests/fixtures/pdf/real-journal-articles/README.md text eol=lf",
        "tests/fixtures/pdf/real-journal-articles/manifest.json text eol=lf",
    ]

    source_path = Path(__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    forbidden_imports = {
        "ftplib",
        "httpx",
        "importlib",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    forbidden_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "getattr",
        "setattr",
    }
    imported_roots: set[str] = set()
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.partition(".")[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.partition(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    absolute_home_prefix = "/" + "Users/"
    assert imported_roots.isdisjoint(forbidden_imports)
    assert called_names.isdisjoint(forbidden_calls)
    assert all(
        not value.startswith(absolute_home_prefix) for value in string_literals
    )
    assert absolute_home_prefix not in README_PATH.read_text(encoding="utf-8")

    package_configuration = (ROOT / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert '[tool.setuptools.packages.find]\nwhere = ["src/python"]\n' in (
        package_configuration
    )
    assert not FIXTURE_DIRECTORY.is_relative_to(ROOT / "src" / "python")
    assert not source_path.is_relative_to(ROOT / "src" / "python")
