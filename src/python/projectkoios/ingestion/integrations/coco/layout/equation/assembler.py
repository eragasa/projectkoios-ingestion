"""Effectful equation assembly from projected COCO formula evidence."""

from __future__ import annotations

from io import BytesIO

from projectkoios.ingestion.equations.assembly.identity import (
    EQUATION_ASSEMBLY_CONTRACT_VERSION,
    equation_assembly_id,
)
from projectkoios.ingestion.equations.assembly.kind import EquationAssemblyKind
from projectkoios.ingestion.equations.assembly.model import EquationAssembly
from projectkoios.ingestion.equations.assembly.result import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.equations.detection import EquationEvidenceStatus
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.pdf.models import PageRegionSelection
from projectkoios.ingestion.pdf.renderer import PageRegionRenderer
from projectkoios.ingestion.sha256.verifier import SHA256Verifier

from .result import CocoLayoutEquationProjectionResult


class CocoLayoutEquationAssembler:
    """Render one display assembly per projected layout-formula candidate."""

    __slots__ = ("renderer",)

    def __init__(self, *, renderer: PageRegionRenderer) -> None:
        if not isinstance(renderer, PageRegionRenderer):
            raise TypeError("renderer must be PageRegionRenderer")
        self.renderer = renderer

    def assemble(
        self,
        projection: CocoLayoutEquationProjectionResult,
        content: bytes,
    ) -> EquationAssemblyResult:
        """Render exact source boxes and return recognition-ready assemblies."""
        if type(projection) is not CocoLayoutEquationProjectionResult:
            raise TypeError(
                "projection must be CocoLayoutEquationProjectionResult"
            )
        if type(content) is not bytes:
            raise TypeError("content must be immutable bytes")
        document = projection.request.document
        if not SHA256Verifier.verify(
            content=content,
            expected=document.source.content_hash,
        ):
            raise ValueError("equation assembly requires exact PDF bytes")
        candidates = tuple(projection.candidates)
        selections = tuple(
            PageRegionSelection.for_bounding_box(
                document.source,
                candidate.source_span.page_index,
                candidate.source_span.bounding_box,
            )
            for candidate in candidates
            if candidate.source_span.bounding_box is not None
        )
        if len(selections) != len(candidates):
            raise ValueError("equation candidate source geometry is missing")
        rendered = (
            self.renderer.render(
                document.source,
                BytesIO(content),
                selections,
            )
            if selections
            else ()
        )
        if len(rendered) != len(candidates):
            raise ValueError("renderer returned the wrong region count")
        pages = {page.page_index: page for page in document.pages}
        assemblies: list[EquationAssembly] = []
        for candidate, selection, region in zip(
            candidates, selections, rendered, strict=True
        ):
            page = pages[candidate.source_span.page_index]
            if (
                region.source_id != document.source.source_id
                or region.source_blob_id != document.source.blob_id
                or region.source_content_hash != document.source.content_hash
                or region.page_index != candidate.source_span.page_index
                or region.printed_page_label
                != candidate.source_span.printed_page_label
                or region.source_bounding_box != selection.bounding_box
                or region.coordinate_system != page.coordinate_system
                or region.page_rotation_degrees != page.rotation_degrees
                or region.selection_was_full_page
            ):
                raise ValueError(
                    "rendered equation region differs from its candidate"
                )
            statuses = (EquationEvidenceStatus.PROPOSED,)
            candidate_ids = (candidate.candidate_id,)
            prefilter_reasons = ("layout_detector_without_native_text",)
            assembly_id = equation_assembly_id(
                projection.result_id,
                candidate_ids,
                statuses,
                region.region_id,
                "",
                prefilter_reasons,
                False,
            )
            assemblies.append(
                EquationAssembly(
                    assembly_id=assembly_id,
                    detection_result_id=projection.result_id,
                    candidate_ids=candidate_ids,
                    detector_evidence_statuses=statuses,
                    kind=EquationAssemblyKind.DISPLAY,
                    page_index=region.page_index,
                    printed_page_label=candidate.source_span.printed_page_label,
                    source_spans=(candidate.source_span,),
                    source_block_ids=(),
                    raw_fragments=("",),
                    sanitized_native_text="",
                    control_character_count=0,
                    source_labels=(),
                    preceding_context_text=None,
                    following_context_text=None,
                    rendered_region=region,
                    prefilter_reasons=prefilter_reasons,
                    rejected=False,
                )
            )
        values = tuple(assemblies)
        artifact_id = stable_id(
            "equation-assembly-artifact",
            EQUATION_ASSEMBLY_CONTRACT_VERSION,
            document.source.source_id,
            document.source.content_hash,
            document.document_id,
            projection.result_id,
            tuple(value.assembly_id for value in values),
        )
        return EquationAssemblyResult(
            artifact_id=artifact_id,
            source_id=document.source.source_id,
            source_content_hash=document.source.content_hash,
            document_id=document.document_id,
            detection_result_id=projection.result_id,
            assemblies=values,
        )
