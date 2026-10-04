from projectkoios.ingestion.transcription.item.kind import TranscriptionItemKind


def test__transcription_item_kind__names_retained_item_roles() -> None:
    assert tuple(value.value for value in TranscriptionItemKind) == (
        "page_anchor",
        "heading",
        "prose",
        "equation",
        "table",
        "figure",
    )
