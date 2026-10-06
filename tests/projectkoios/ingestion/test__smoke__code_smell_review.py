from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke


def _repository_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src/python/projectkoios/ingestion"
        ).is_dir():
            return candidate
    raise RuntimeError("repository root is not discoverable")


_SOURCE_ROOT = _repository_root() / "src/python/projectkoios/ingestion"
_MIGRATED_SCOPES = (
    _SOURCE_ROOT / "articles",
    _SOURCE_ROOT / "base",
    _SOURCE_ROOT / "storage",
    _SOURCE_ROOT / "integrations/mongodb",
    _SOURCE_ROOT / "integrations/sqlite",
    _SOURCE_ROOT / "documents/structure",
    _SOURCE_ROOT / "figures/relevance",
    _SOURCE_ROOT / "ocr",
    _SOURCE_ROOT / "reconciliation",
    _SOURCE_ROOT / "tables/structure",
    _SOURCE_ROOT / "textbooks",
    _SOURCE_ROOT / "transcription",
)


def _semantic_name(name: str) -> str:
    return name[1:] if name.startswith("_") else name


def _source_owned_paths(root: Path) -> Iterator[Path]:
    # Runtime caches can preserve directories after their source modules move.
    for path in root.rglob("*"):
        if "__pycache__" in path.parts:
            continue
        if path.is_dir() and not any(
            child.name != "__pycache__" for child in path.iterdir()
        ):
            continue
        yield path


def test__smoke__runtime_cache_only_directories_are_not_source_paths(
    tmp_path: Path,
) -> None:
    runtime_cache = tmp_path / "stale_flattened_name" / "__pycache__"
    runtime_cache.mkdir(parents=True)
    (runtime_cache / "module.cpython-314.pyc").touch()

    assert tuple(_source_owned_paths(tmp_path)) == ()


def test__smoke__migrated_scopes_have_no_flattened_semantic_names() -> None:
    flattened: list[str] = []
    for root in _MIGRATED_SCOPES:
        for path in _source_owned_paths(root):
            name = path.stem if path.is_file() else path.name
            if path.name == "__init__.py":
                continue
            if "_" in _semantic_name(name):
                flattened.append(str(path.relative_to(_SOURCE_ROOT)))

    assert flattened == []


def test__smoke__migrated_scopes_have_no_redundant_module_paths() -> None:
    redundant = sorted(
        str(path.relative_to(_SOURCE_ROOT))
        for root in _MIGRATED_SCOPES
        for path in root.rglob("*.py")
        if path.name != "__init__.py" and path.parent.name == path.stem
    )

    assert redundant == []


def test__smoke__migrated_package_initializers_are_ownership_markers() -> None:
    invalid: list[str] = []
    for root in _MIGRATED_SCOPES:
        for path in root.rglob("__init__.py"):
            body = ast.parse(path.read_text()).body
            is_docstring_only = (
                len(body) == 1
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            )
            if not is_docstring_only:
                invalid.append(str(path.relative_to(_SOURCE_ROOT)))

    assert invalid == []


def test__smoke__direct_immutable_records_are_frozen_dataclasses() -> None:
    invalid: list[str] = []
    for root in _MIGRATED_SCOPES:
        for path in root.rglob("*.py"):
            module = ast.parse(path.read_text())
            for node in module.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                bases = tuple(ast.unparse(base) for base in node.bases)
                directly_immutable = any(
                    base.endswith("AbstractImmutableDataObject")
                    for base in bases
                )
                if not directly_immutable or node.name.startswith("Abstract"):
                    continue
                decorators = tuple(
                    ast.unparse(decorator).replace(" ", "")
                    for decorator in node.decorator_list
                )
                if not any(
                    decorator.startswith("dataclass(")
                    and "frozen=True" in decorator
                    for decorator in decorators
                ):
                    invalid.append(
                        f"{path.relative_to(_SOURCE_ROOT)}:{node.name}"
                    )

    assert invalid == []
