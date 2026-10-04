from projectkoios.ingestion.transcription.order.status import (
    TranscriptionOrderStatus,
)


def test__transcription_order_status__retains_uncertainty() -> None:
    assert (
        TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER.value
        == "uncertain_source_order"
    )
