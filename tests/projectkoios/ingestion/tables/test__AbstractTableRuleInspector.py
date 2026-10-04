"""Table-rule inspector boundary tests."""

import inspect

import pytest
from projectkoios.ingestion import (
    PyMuPdfTableRuleInspector,
    TableRuleInspector,
)


def test__table_rule_inspector__is_abstract() -> None:
    assert inspect.isabstract(TableRuleInspector)
    with pytest.raises(TypeError):
        TableRuleInspector()


def test__pymupdf_table_rule_inspector__inherits_nominal_boundary() -> None:
    assert issubclass(PyMuPdfTableRuleInspector, TableRuleInspector)
