"""Figure inspector boundary tests."""

import inspect

import pytest
from projectkoios.ingestion import FigureInspector, PyMuPdfFigureInspector


def test__figure_inspector__is_abstract() -> None:
    assert inspect.isabstract(FigureInspector)
    with pytest.raises(TypeError):
        FigureInspector()


def test__pymupdf_figure_inspector__inherits_nominal_boundary() -> None:
    assert issubclass(PyMuPdfFigureInspector, FigureInspector)
