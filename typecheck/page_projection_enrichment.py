"""Architecture checker for the page-projection-enrichment source slice."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from mypy.errors import CompileError
from mypy.options import Options
from mypy.plugin import Plugin

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_TARGET = (
    _REPOSITORY_ROOT
    / "src/python/projectkoios/ingestion/page/projection/enrichment"
)
_ACTION_BASES = frozenset(
    {
        "DataObjectActionizer",
        "DataObjectActionRequest",
        "DataObjectActionResult",
    }
)
_RECORD_SUFFIXES = (
    "Binding",
    "Enrichment",
    "Identity",
    "Inventory",
    "Limitation",
    "Unavailable",
    "Warning",
)
_DIAGNOSTIC_PREFIX = "projectkoios-page-projection-enrichment"


@dataclass(frozen=True, slots=True)
class ArchitectureDiagnostic:
    """One stable source diagnostic emitted by the local checker."""

    path: Path
    line: int
    column: int
    code: str
    message: str

    def render(self, *, relative_to: Path | None = None) -> str:
        """Render one mypy-compatible diagnostic line."""
        path = self.path
        if relative_to is not None:
            try:
                path = path.relative_to(relative_to)
            except ValueError:
                pass
        return (
            f"{path}:{self.line}:{self.column}: error: {self.message} "
            f"[{self.code}]"
        )


class _ArchitectureVisitor(ast.NodeVisitor):
    """Inspect classes while ignoring tuples and helper functions."""

    def __init__(self, *, path: Path) -> None:
        self._path = path
        self._class_depth = 0
        self._function_depth = 0
        self.diagnostics: list[ArchitectureDiagnostic] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        """Reject opaque or multi-operation class shapes."""
        nested = self._class_depth > 0 or self._function_depth > 0
        private = node.name.startswith("_")
        if private:
            self._report(
                node=node,
                code=f"{_DIAGNOSTIC_PREFIX}-private-class",
                message="private classes are prohibited in this source slice",
            )
        if nested:
            self._report(
                node=node,
                code=f"{_DIAGNOSTIC_PREFIX}-nested-class",
                message="nested classes are prohibited in this source slice",
            )

        public_methods = tuple(
            statement.name
            for statement in node.body
            if isinstance(statement, (ast.AsyncFunctionDef, ast.FunctionDef))
            and not statement.name.startswith("_")
        )
        terminal_bases = {
            value
            for value in (_terminal_name(base) for base in node.bases)
            if value is not None
        }
        is_actionizer = (
            "DataObjectActionizer" in terminal_bases
            or node.name.endswith("Actionizer")
        )
        is_facade = node.name.endswith(("Facade", "Façade"))
        if (is_actionizer and public_methods != ("action",)) or (
            is_facade and len(public_methods) > 1
        ):
            self._report(
                node=node,
                code=f"{_DIAGNOSTIC_PREFIX}-multi-verb-class",
                message=(
                    "actionizers and facades may expose only one public verb"
                ),
            )

        if not private and not nested:
            if not _is_taxonomy_class(
                node=node,
                terminal_bases=terminal_bases,
            ):
                self._report(
                    node=node,
                    code=f"{_DIAGNOSTIC_PREFIX}-non-taxonomy-class",
                    message=(
                        "class is outside the permitted action, enum, and "
                        "immutable-record taxonomy"
                    ),
                )

        self._class_depth += 1
        self.generic_visit(node)
        self._class_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Track function nesting while permitting helper functions."""
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def visit_AsyncFunctionDef(  # noqa: N802
        self, node: ast.AsyncFunctionDef
    ) -> None:
        """Track async function nesting while permitting helper functions."""
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def _report(self, *, node: ast.ClassDef, code: str, message: str) -> None:
        """Append one deterministic diagnostic."""
        self.diagnostics.append(
            ArchitectureDiagnostic(
                path=self._path,
                line=node.lineno,
                column=node.col_offset + 1,
                code=code,
                message=message,
            )
        )


def _terminal_name(expression: ast.expr) -> str | None:
    """Return the terminal identifier of a base or decorator expression."""
    if isinstance(expression, ast.Call):
        return _terminal_name(expression.func)
    if isinstance(expression, ast.Subscript):
        return _terminal_name(expression.value)
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        return expression.attr
    return None


def _is_taxonomy_class(*, node: ast.ClassDef, terminal_bases: set[str]) -> bool:
    """Return whether a top-level public class has an allowed semantic role."""
    if terminal_bases.intersection(_ACTION_BASES):
        expected_suffix = {
            "DataObjectActionizer": "Actionizer",
            "DataObjectActionRequest": "Request",
            "DataObjectActionResult": "Result",
        }
        return all(
            node.name.endswith(expected_suffix[base])
            for base in terminal_bases.intersection(_ACTION_BASES)
        )
    if "StrEnum" in terminal_bases:
        return True
    decorators = {
        value
        for value in (_terminal_name(item) for item in node.decorator_list)
        if value is not None
    }
    return "dataclass" in decorators and node.name.endswith(_RECORD_SUFFIXES)


def scan_source(
    *, path: Path, source: str
) -> tuple[ArchitectureDiagnostic, ...]:
    """Return architecture diagnostics for one Python source string."""
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        return (
            ArchitectureDiagnostic(
                path=path,
                line=error.lineno or 1,
                column=error.offset or 1,
                code=f"{_DIAGNOSTIC_PREFIX}-syntax",
                message=error.msg,
            ),
        )
    visitor = _ArchitectureVisitor(path=path)
    visitor.visit(tree)
    return tuple(visitor.diagnostics)


def scan_paths(*, paths: Iterable[Path]) -> tuple[ArchitectureDiagnostic, ...]:
    """Return sorted architecture diagnostics for Python files and trees."""
    source_paths: set[Path] = set()
    for path in paths:
        if path.is_dir():
            source_paths.update(path.rglob("*.py"))
        elif path.suffix == ".py":
            source_paths.add(path)
    diagnostics: list[ArchitectureDiagnostic] = []
    for path in sorted(source_paths):
        diagnostics.extend(
            scan_source(path=path, source=path.read_text(encoding="utf-8"))
        )
    return tuple(diagnostics)


def scan_actual_slice() -> tuple[ArchitectureDiagnostic, ...]:
    """Scan the owned production slice loaded by normal mypy execution."""
    return scan_paths(paths=(_TARGET,))


class PageProjectionEnrichmentPlugin(Plugin):
    """Fail mypy startup when the owned source slice violates its taxonomy."""

    def __init__(self, options: Options) -> None:
        super().__init__(options)
        diagnostics = scan_actual_slice()
        if diagnostics:
            raise CompileError(
                [
                    diagnostic.render(relative_to=_REPOSITORY_ROOT)
                    for diagnostic in diagnostics
                ]
            )


def plugin(version: str) -> type[Plugin]:
    """Return the repository-local plugin for every supported mypy version."""
    del version
    return PageProjectionEnrichmentPlugin


def main(argv: Sequence[str] | None = None) -> int:
    """Run the checker directly for diagnostics and fixture development."""
    paths = tuple(Path(value) for value in (argv or (str(_TARGET),)))
    diagnostics = scan_paths(paths=paths)
    for diagnostic in diagnostics:
        print(diagnostic.render(relative_to=_REPOSITORY_ROOT))
    return bool(diagnostics)


if __name__ == "__main__":
    raise SystemExit(main())
