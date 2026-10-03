import inspect

from projectkoios.ingestion import (
    AbstractTranscriptPage as RootAbstractTranscriptPage,
)
from projectkoios.ingestion.clean_transcript import CleanTranscriptPage
from projectkoios.ingestion.documents.page.base import AbstractDocumentPage
from projectkoios.ingestion.transcripts.page.base import AbstractTranscriptPage


def test__abstract_transcript_page__specializes_document_page() -> None:
    assert RootAbstractTranscriptPage is AbstractTranscriptPage
    assert issubclass(AbstractTranscriptPage, AbstractDocumentPage)
    assert inspect.isabstract(AbstractTranscriptPage)
    assert issubclass(CleanTranscriptPage, AbstractTranscriptPage)
    assert not inspect.isabstract(CleanTranscriptPage)


def test__clean_page__provides_document_and_transcript_views() -> None:
    page = CleanTranscriptPage.create(
        page_index=3,
        printed_page_label="4",
        block_record_ids=("block-record",),
        text="Clean page text",
    )

    assert page.transcript_page_id == page.page_id
    assert page.document_page_id == page.page_id
    assert page.transcript_block_ids == ("block-record",)
    assert page.document_block_ids == ("block-record",)
    assert page.transcript_text == "Clean page text"
    assert page.document_text == "Clean page text"
