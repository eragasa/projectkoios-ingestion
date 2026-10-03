from __future__ import annotations

import inspect

from projectkoios.ingestion.equations.base import AbstractEquation
from projectkoios.ingestion.equations.image.base import AbstractEquationImage


def test__abstract_equation_image__is_a_format_neutral_abc() -> None:
    assert inspect.isabstract(AbstractEquationImage)
    assert issubclass(AbstractEquationImage, AbstractEquation)
    assert AbstractEquationImage.MAX_CONTENT_BYTES == 100_000_000
