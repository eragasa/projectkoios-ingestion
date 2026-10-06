from projectkoios.ingestion.transcription.status.order import (
    TranscriptionOrderStatus,
)


def test__transcription_order_status__retains_uncertainty() -> None:
    assert (
        TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER.value
        == "uncertain_source_order"
    )
