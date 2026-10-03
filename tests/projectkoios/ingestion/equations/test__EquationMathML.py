from __future__ import annotations

import pytest
from projectkoios.ingestion.equations.mathml import EquationMathML


def test__equation_mathml__retains_exact_well_formed_mathml() -> None:
    content = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        "<mi>E</mi><mo>=</mo><mi>m</mi><msup><mi>c</mi><mn>2</mn></msup>"
        "</math>"
    )
    equation = EquationMathML(
        source_ids=("equation-latex:sha256:source",),
        mathml=content,
    )

    assert equation.mathml == content
    assert equation.equation_source_ids == (
        "equation-latex:sha256:source",
    )
    assert hash(equation)


def test__equation_mathml__rejects_non_math_root() -> None:
    with pytest.raises(ValueError, match="root must be math"):
        EquationMathML(
            source_ids=("equation-latex:sha256:source",),
            mathml="<div>not math</div>",
        )
