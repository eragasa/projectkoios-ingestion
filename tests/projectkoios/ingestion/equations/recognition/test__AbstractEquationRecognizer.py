from __future__ import annotations

import inspect

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.equations.recognition.base import (
    AbstractEquationRecognizer,
)


def test__abstract_equation_recognizer__is_vendor_neutral_actionizer() -> None:
    assert inspect.isabstract(AbstractEquationRecognizer)
    assert issubclass(AbstractEquationRecognizer, DataObjectActionizer)
