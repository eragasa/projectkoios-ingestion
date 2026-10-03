from projectkoios.ingestion.equations.recognition.checkpoint.checkpoint import (
    EquationRecognitionCheckpoint,
)
from projectkoios.ingestion.equations.recognition.checkpoint.policy import (
    defer_equation_recognition,
)
from projectkoios.ingestion.equations.recognition.checkpoint.state import (
    EquationRecognitionWorkState,
)


def test__recognition_deferral__only_changes_untouched_pending_work() -> None:
    pending = defer_equation_recognition(
        EquationRecognitionCheckpoint(EquationRecognitionWorkState.PENDING)
    )
    complete = defer_equation_recognition(
        EquationRecognitionCheckpoint(EquationRecognitionWorkState.COMPLETE)
    )
    failed = defer_equation_recognition(
        EquationRecognitionCheckpoint(
            EquationRecognitionWorkState.FAILED,
            error="bounded recognizer failure",
        )
    )

    assert pending.resulting_state is EquationRecognitionWorkState.NOT_REQUESTED
    assert pending.changed is True
    assert complete.resulting_state is EquationRecognitionWorkState.COMPLETE
    assert complete.changed is False
    assert failed.resulting_state is EquationRecognitionWorkState.FAILED
    assert failed.preserved_error == "bounded recognizer failure"
    assert failed.changed is False
