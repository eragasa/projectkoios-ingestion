import inspect

from projectkoios.ingestion import AbstractTranscript as RootAbstractTranscript
from projectkoios.ingestion.clean_transcript import CleanTranscript
from projectkoios.ingestion.documents.base import AbstractDocument
from projectkoios.ingestion.transcripts.base import AbstractTranscript


def test__abstract_transcript__specializes_abstract_document() -> None:
    assert RootAbstractTranscript is AbstractTranscript
    assert issubclass(AbstractTranscript, AbstractDocument)
    assert inspect.isabstract(AbstractTranscript)
    assert issubclass(CleanTranscript, AbstractTranscript)
    assert not inspect.isabstract(CleanTranscript)
