from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import (
    DataObjectActionRequest,
)
from projectkoios.ingestion.equations.detection import (
    EquationDetectionResult,
)
from projectkoios.ingestion.figures import (
    FigureDetectionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    ExtractedDocument,
)
from projectkoios.ingestion.structure import (
    StructureAnalysis,
)
from projectkoios.ingestion.tables.structure.result import TableStructureResult
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.configuration import (  # noqa: E501
    TranscriptionConfiguration,
)
from projectkoios.ingestion.transcription.request_validation import (
    TranscriptionRequestValidation,
)


@dataclass(frozen=True)
class StructuredTranscriptionRequest(
    DataObjectActionRequest, AbstractTranscriptionDataObject
):
    input_id: str
    document_evidence_id: str
    document: ExtractedDocument
    structure_analysis: StructureAnalysis
    equation_detection_result: EquationDetectionResult
    table_structure_result: TableStructureResult
    figure_detection_result: FigureDetectionResult
    configuration: TranscriptionConfiguration
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        document: ExtractedDocument,
        structure_analysis: StructureAnalysis,
        equation_detection_result: EquationDetectionResult,
        table_structure_result: TableStructureResult,
        figure_detection_result: FigureDetectionResult,
        configuration: TranscriptionConfiguration | None = None,
    ) -> StructuredTranscriptionRequest:
        actual = configuration or TranscriptionConfiguration()
        document_evidence_id = (
            StructuredTranscriptionRequest.document_evidence_identity(document)
        )
        return cls(
            input_id=StructuredTranscriptionRequest.identity_for(
                document_evidence_id,
                document,
                structure_analysis,
                equation_detection_result,
                table_structure_result,
                figure_detection_result,
                actual,
            ),
            document_evidence_id=document_evidence_id,
            document=document,
            structure_analysis=structure_analysis,
            equation_detection_result=equation_detection_result,
            table_structure_result=table_structure_result,
            figure_detection_result=figure_detection_result,
            configuration=actual,
        )

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != AbstractTranscriptionDataObject.CONTRACT_VERSION
        ):
            raise ValueError("unsupported transcription input version")
        validation = TranscriptionRequestValidation.validate(
            self.document,
            self.structure_analysis,
            self.equation_detection_result,
            self.table_structure_result,
            self.figure_detection_result,
            self.configuration,
        )
        if validation.document_id != self.document.document_id:
            raise ValueError("transcription request validation is inconsistent")
        AbstractTranscriptionDataObject.validate_identity_fields(
            self.document_evidence_id
        )
        expected_document_evidence_id = (
            StructuredTranscriptionRequest.document_evidence_identity(
                self.document
            )
        )
        if self.document_evidence_id != expected_document_evidence_id:
            raise ValueError(
                "transcription document evidence ID is inconsistent"
            )
        expected = StructuredTranscriptionRequest.identity_for(
            self.document_evidence_id,
            self.document,
            self.structure_analysis,
            self.equation_detection_result,
            self.table_structure_result,
            self.figure_detection_result,
            self.configuration,
        )
        if self.input_id != expected:
            raise ValueError("transcription input ID is inconsistent")

    @property
    def request_id(self) -> str:
        return self.input_id

    @classmethod
    def document_evidence_identity(cls, document: ExtractedDocument) -> str:
        return stable_id("structured-transcription-document-evidence", document)

    @classmethod
    def identity_for(
        cls,
        document_evidence_id: str,
        document: ExtractedDocument,
        structure_analysis: StructureAnalysis,
        equation_result: EquationDetectionResult,
        table_result: TableStructureResult,
        figure_result: FigureDetectionResult,
        configuration: TranscriptionConfiguration,
    ) -> str:
        return stable_id(
            "structured-transcription-input",
            AbstractTranscriptionDataObject.CONTRACT_VERSION,
            document_evidence_id,
            document.document_id,
            document.source.source_id,
            document.source.blob_id,
            structure_analysis.analysis_id,
            equation_result.result_id,
            table_result.result_id,
            figure_result.result_id,
            configuration.identity_parts(),
        )
