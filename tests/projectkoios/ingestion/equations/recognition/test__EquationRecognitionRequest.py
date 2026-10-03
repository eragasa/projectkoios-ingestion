from __future__ import annotations

import pytest
from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)


def test__equation_recognition_request__is_an_action_request() -> None:
    assert issubclass(EquationRecognitionRequest, DataObjectActionRequest)
    assert issubclass(EquationRecognitionRequest, AbstractImmutableDataObject)


def test__equation_recognition_request__requires_nominal_assembly() -> None:
    with pytest.raises(TypeError, match="EquationAssemblyResult"):
        EquationRecognitionRequest(
            request_id="pix2tex-recognition-request:invalid",
            assembly_artifact=object(),  # type: ignore[arg-type]
            processor_identity=object(),  # type: ignore[arg-type]
        )
