from __future__ import annotations

import pytest
from projectkoios.ingestion.equations.katex import EquationKatex
from projectkoios.ingestion.equations.latex import EquationLatex
from projectkoios.ingestion.equations.mathml import EquationMathML
from projectkoios.ingestion.sha256.verifier import SHA256Verifier


def _representations() -> tuple[EquationLatex, EquationMathML]:
    latex = EquationLatex(
        source_ids=("equation-image:sha256:source",),
        latex="E = mc^2",
    )
    mathml = EquationMathML(
        source_ids=(latex.equation_id,),
        mathml="<math><mi>E</mi></math>",
    )
    return latex, mathml


def test__equation_katex__binds_rendering_to_latex_and_mathml() -> None:
    latex, mathml = _representations()
    html = '<span class="katex">E = mc²</span>'
    equation = EquationKatex(
        latex=latex,
        mathml=mathml,
        html=html,
        katex_version="0.16.22",
    )

    assert equation.equation_source_ids == (
        latex.equation_id,
        mathml.equation_id,
    )
    assert SHA256Verifier.verify(
        content=html.encode(), expected=equation.html_sha256
    )
    assert hash(equation)


def test__equation_katex__rejects_unrelated_mathml() -> None:
    latex, _ = _representations()
    unrelated = EquationMathML(
        source_ids=("equation-latex:sha256:other",),
        mathml="<math><mi>x</mi></math>",
    )

    with pytest.raises(ValueError, match="does not derive"):
        EquationKatex(
            latex=latex,
            mathml=unrelated,
            html="<span>x</span>",
            katex_version="0.16.22",
        )
