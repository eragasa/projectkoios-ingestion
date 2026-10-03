import inspect

from projectkoios.ingestion import (
    AbstractTranscriptBlock as RootAbstractTranscriptBlock,
)
from projectkoios.ingestion.clean_transcript import CleanTranscriptBlock
from projectkoios.ingestion.documents.block.base import AbstractDocumentBlock
from projectkoios.ingestion.transcripts.block.base import (
    AbstractTranscriptBlock,
)


def test__abstract_transcript_block__specializes_document_block() -> None:
    assert RootAbstractTranscriptBlock is AbstractTranscriptBlock
    assert issubclass(AbstractTranscriptBlock, AbstractDocumentBlock)
    assert inspect.isabstract(AbstractTranscriptBlock)
    assert issubclass(CleanTranscriptBlock, AbstractTranscriptBlock)
    assert not inspect.isabstract(CleanTranscriptBlock)


def test__clean_block__provides_document_and_transcript_views() -> None:
    block = CleanTranscriptBlock.create(
        block_id="source-block",
        page_index=3,
        printed_page_label="4",
        order_index=7,
        raw_text="Raw text",
        clean_text="Clean text",
        source_spans=(),
        transformations=(),
        dehyphenation_decision_ids=(),
        page_number_classification_id=None,
        publisher_classification_id=None,
        private_use_finding_ids=(),
    )

    assert block.transcript_block_id == block.record_id
    assert block.document_block_id == block.record_id
    assert block.transcript_text == "Clean text"
    assert block.document_text == "Clean text"
