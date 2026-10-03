from __future__ import annotations

import pytest
from projectkoios.ingestion.equations.base import AbstractEquation
from projectkoios.ingestion.equations.latex import EquationLatex


def test__equation_latex__retains_exact_text_and_trace() -> None:
    equation = EquationLatex(
        source_ids=("equation-image:sha256:source",),
        latex="  E = mc^2  ",
    )

    assert isinstance(equation, AbstractEquation)
    assert equation.latex == "  E = mc^2  "
    assert equation.equation_source_ids == (
        "equation-image:sha256:source",
    )
    assert hash(equation)


def test__equation_latex__rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="size is out of bounds"):
        EquationLatex(
            source_ids=("equation-image:sha256:source",),
            latex="   ",
        )
