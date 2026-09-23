from __future__ import annotations

import inspect

from projectkoios.ingestion.article_structure import (
    DeterministicArticleStructureAnalyzer,
)
from projectkoios.ingestion.base import (
    BaseArticleStructureAnalyzer,
    BaseCleanTranscriptProjector,
    BaseCleanTranscriptV2Projector,
    BaseDerivationAuditValidator,
    BaseDeterministicProcessor,
    BaseDocumentPersistanceStore,
    BaseDocumentPersister,
    BaseEquationAssembler,
    BaseEquationCandidateDetector,
    BaseEquationRecognizer,
    BaseFigureCandidateDetector,
    BaseFigureInspector,
    BaseOcrReconciler,
    BasePageLayoutProcessor,
    BasePageRegionRenderer,
    BaseProcessedDocumentPersistanceStore,
    BaseProcessedDocumentPersister,
    BaseProcessingCoordinator,
    BaseSourceExtractor,
    BaseStructuredTranscriptionComposer,
    BaseTableCandidateDetector,
    BaseTableRuleInspector,
    BaseTableStructureReconstructor,
)
from projectkoios.ingestion.deterministic import DeterministicProcessor
from projectkoios.ingestion.equation_enrichment import (
    DeterministicEquationAssembler,
    Pix2TexCliEquationRecognizer,
)
from projectkoios.ingestion.equations import (
    DeterministicEquationCandidateDetector,
)
from projectkoios.ingestion.figures import (
    DeterministicFigureCandidateDetector,
    PyMuPdfFigureInspector,
)
from projectkoios.ingestion.layout import DeterministicLayoutProcessor
from projectkoios.ingestion.pdf import PyMuPdfExtractor, PyMuPdfRegionRenderer
from projectkoios.ingestion.pilot.deterministic import (
    PilotDeterministicProcessor,
)
from projectkoios.ingestion.processing import BoundedProcessingCoordinator
from projectkoios.ingestion.provenance import DerivationAuditValidator
from projectkoios.ingestion.reconciliation import DeterministicOCRReconciler
from projectkoios.ingestion.table_structure import (
    DeterministicTableStructureReconstructor,
)
from projectkoios.ingestion.tables import (
    DeterministicTableCandidateDetector,
    PyMuPdfTableRuleInspector,
)
from projectkoios.ingestion.transcript_projection import (
    DeterministicCleanTranscriptProjector,
)
from projectkoios.ingestion.transcript_v2 import (
    DeterministicCleanTranscriptV2Projector,
)
from projectkoios.ingestion.transcription import (
    DeterministicStructuredTranscriptionComposer,
)


def test__component_implementations__inherit_their_base_contracts() -> None:
    relationships = (
        (PyMuPdfExtractor, BaseSourceExtractor),
        (DeterministicLayoutProcessor, BasePageLayoutProcessor),
        (PyMuPdfRegionRenderer, BasePageRegionRenderer),
        (DeterministicOCRReconciler, BaseOcrReconciler),
        (
            DeterministicArticleStructureAnalyzer,
            BaseArticleStructureAnalyzer,
        ),
        (
            DeterministicEquationCandidateDetector,
            BaseEquationCandidateDetector,
        ),
        (DeterministicEquationAssembler, BaseEquationAssembler),
        (Pix2TexCliEquationRecognizer, BaseEquationRecognizer),
        (PyMuPdfTableRuleInspector, BaseTableRuleInspector),
        (DeterministicTableCandidateDetector, BaseTableCandidateDetector),
        (
            DeterministicTableStructureReconstructor,
            BaseTableStructureReconstructor,
        ),
        (PyMuPdfFigureInspector, BaseFigureInspector),
        (DeterministicFigureCandidateDetector, BaseFigureCandidateDetector),
        (
            DeterministicStructuredTranscriptionComposer,
            BaseStructuredTranscriptionComposer,
        ),
        (
            DeterministicCleanTranscriptProjector,
            BaseCleanTranscriptProjector,
        ),
        (
            DeterministicCleanTranscriptV2Projector,
            BaseCleanTranscriptV2Projector,
        ),
        (BoundedProcessingCoordinator, BaseProcessingCoordinator),
        (DerivationAuditValidator, BaseDerivationAuditValidator),
    )

    assert all(
        issubclass(implementation, base)
        for implementation, base in relationships
    )


def test__base_component_stubs__remain_abstract() -> None:
    base_types = (
        BaseDocumentPersistanceStore,
        BaseDocumentPersister,
        BaseProcessedDocumentPersistanceStore,
        BaseProcessedDocumentPersister,
    )

    assert all(inspect.isabstract(base_type) for base_type in base_types)


def test__deterministic_composition__inherits_base_contract() -> None:
    assert issubclass(DeterministicProcessor, BaseDeterministicProcessor)
    assert issubclass(PilotDeterministicProcessor, DeterministicProcessor)
    assert (
        PilotDeterministicProcessor.process
        is not DeterministicProcessor.process
    )
