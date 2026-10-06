from projectkoios.ingestion.transcription.kind.source.object import (
    TranscriptionSourceObjectKind,
)


def test__transcription_source_object_kind__names_retained_sources() -> None:
    assert (
        TranscriptionSourceObjectKind.TABLE_STRUCTURE.value == "table_structure"
    )
