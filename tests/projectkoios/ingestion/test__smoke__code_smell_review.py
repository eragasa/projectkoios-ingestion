from __future__ import annotations

import ast
import inspect
from collections.abc import Iterator
from dataclasses import dataclass, is_dataclass
from importlib import import_module
from pathlib import Path
from typing import get_type_hints

import pytest
from projectkoios.base import DataObjectModel
from projectkoios.ingestion.articles.structure.actionizer import (
    DeterministicArticleStructureActionizer,
)
from projectkoios.ingestion.articles.structure.request import (
    ArticleStructureRequest,
)
from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.structure import StructureAnalysis

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


@dataclass(frozen=True, slots=True)
class _ActionizedOperation:
    name: str
    request_type: type[object]
    request_base: type[object]
    actionizer_type: type[object]
    actionizer_base: type[object]
    result_type: type[object]
    result_base: type[object]
    configuration_field: str | None = None
    stateless_actionizer: bool = False


_ACTIONIZED_OPERATIONS = (
    _ActionizedOperation(
        name="article_structure",
        request_type=ArticleStructureRequest,
        request_base=ConfigurableDataObjectActionRequest,
        actionizer_type=DeterministicArticleStructureActionizer,
        actionizer_base=ConfigurableDataObjectActionizer,
        result_type=StructureAnalysis,
        result_base=AbstractDataObjectActionResult,
        configuration_field="configuration",
        stateless_actionizer=True,
    ),
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


def _migrated_python_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            {
                path
                for root in _MIGRATED_SCOPES
                for path in root.rglob("*.py")
                if "__pycache__" not in path.parts
            }
        )
    )


def _module_name(path: Path) -> str:
    relative = path.relative_to(_SOURCE_ROOT).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    suffix = ".".join(parts)
    return "projectkoios.ingestion" + (f".{suffix}" if suffix else "")


def test__smoke__runtime_cache_only_directories_are_not_source_paths(
    tmp_path: Path,
) -> None:
    runtime_cache = tmp_path / "stale_flattened_name" / "__pycache__"
    runtime_cache.mkdir(parents=True)
    (runtime_cache / "module.cpython-314.pyc").touch()

    assert tuple(_source_owned_paths(tmp_path)) == ()


def test__smoke__registered_migrated_scopes_exist() -> None:
    missing = sorted(
        str(root.relative_to(_SOURCE_ROOT))
        for root in _MIGRATED_SCOPES
        if not root.is_dir()
    )
    empty = sorted(
        str(root.relative_to(_SOURCE_ROOT))
        for root in _MIGRATED_SCOPES
        if root.is_dir() and not any(root.rglob("*.py"))
    )

    assert missing == []
    assert empty == []


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


def test__smoke__immutable_records_are_frozen_dataclasses() -> None:
    invalid: list[str] = []
    seen: set[type[object]] = set()
    for path in _migrated_python_paths():
        module = import_module(_module_name(path))
        for value in vars(module).values():
            if (
                not inspect.isclass(value)
                or value.__module__ != module.__name__
                or value in seen
            ):
                continue
            seen.add(value)
            if inspect.isabstract(value) or not issubclass(
                value,
                (DataObjectModel, AbstractImmutableDataObject),
            ):
                continue
            parameters = value.__dict__.get("__dataclass_params__")
            if not is_dataclass(value) or not (
                parameters is not None and parameters.frozen
            ):
                invalid.append(f"{module.__name__}:{value.__name__}")

    assert invalid == []


def test__smoke__registered_operations_use_action_contracts() -> None:
    invalid: list[str] = []
    for operation in _ACTIONIZED_OPERATIONS:
        request_type = operation.request_type
        actionizer_type = operation.actionizer_type
        result_type = operation.result_type
        if not issubclass(request_type, operation.request_base):
            invalid.append(f"{operation.name}:request_base")
        if not issubclass(actionizer_type, operation.actionizer_base):
            invalid.append(f"{operation.name}:actionizer_base")
        if not issubclass(result_type, operation.result_base):
            invalid.append(f"{operation.name}:result_base")
        if inspect.isabstract(actionizer_type):
            invalid.append(f"{operation.name}:abstract_actionizer")
        if getattr(actionizer_type, "_is_protocol", False):
            invalid.append(f"{operation.name}:protocol_actionizer")

        request_parameters = request_type.__dict__.get("__dataclass_params__")
        result_parameters = result_type.__dict__.get("__dataclass_params__")
        if not is_dataclass(request_type) or not (
            request_parameters is not None and request_parameters.frozen
        ):
            invalid.append(f"{operation.name}:mutable_request")
        if not is_dataclass(result_type) or not (
            result_parameters is not None and result_parameters.frozen
        ):
            invalid.append(f"{operation.name}:mutable_result")
        if operation.configuration_field is not None and (
            operation.configuration_field
            not in getattr(request_type, "__dataclass_fields__", {})
        ):
            invalid.append(f"{operation.name}:configuration_not_in_request")

        action = actionizer_type.__dict__.get("action")
        if action is None:
            invalid.append(f"{operation.name}:action_not_owned")
            continue
        parameters = inspect.signature(action).parameters
        if tuple(parameters) != ("self", "request") or (
            parameters["request"].kind is not inspect.Parameter.KEYWORD_ONLY
        ):
            invalid.append(f"{operation.name}:action_signature")
        hints = get_type_hints(action)
        if hints.get("request") is not request_type:
            invalid.append(f"{operation.name}:request_annotation")
        if hints.get("return") is not result_type:
            invalid.append(f"{operation.name}:result_annotation")

        if operation.stateless_actionizer:
            instance = actionizer_type()
            if hasattr(instance, "configuration"):
                invalid.append(f"{operation.name}:hidden_configuration")
            for legacy_method in ("analyze", "analyze_with_layout", "process"):
                if hasattr(instance, legacy_method):
                    invalid.append(
                        f"{operation.name}:legacy_{legacy_method}_method"
                    )

    assert invalid == []
