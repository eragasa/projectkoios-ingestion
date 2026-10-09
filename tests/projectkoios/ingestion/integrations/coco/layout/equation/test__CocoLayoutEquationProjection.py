"""Admitted COCO formula projection and assembly tests."""

from __future__ import annotations

import zlib
from collections.abc import Iterable
from dataclasses import replace
from typing import BinaryIO

import pytest
from projectkoios.ingestion.equations.recognition.policy import (
    primary_equation_recognition_ineligibility_reasons,
)
from projectkoios.ingestion.integrations.coco.layout.admission.actionizer import (  # noqa: E501
    CocoLayoutRegionAdmissionActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.admission.configuration import (  # noqa: E501
    CocoLayoutRegionAdmissionConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.admission.evidence import (  # noqa: E501
    CocoLayoutRegionAdmissionDisposition,
)
from projectkoios.ingestion.integrations.coco.layout.admission.request import (  # noqa: E501
    CocoLayoutRegionAdmissionRequest,
)
from projectkoios.ingestion.integrations.coco.layout.equation.actionizer import (  # noqa: E501
    CocoLayoutEquationProjectionActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.equation.assembler import (
    CocoLayoutEquationAssembler,
)
from projectkoios.ingestion.integrations.coco.layout.equation.configuration import (  # noqa: E501
    CocoLayoutEquationProjectionConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.equation.exclusion import (
    CocoLayoutEquationExclusionCode,
)
from projectkoios.ingestion.integrations.coco.layout.equation.request import (
    CocoLayoutEquationProjectionRequest,
)
from projectkoios.ingestion.integrations.pix2tex.policy import (
    pix2tex_primary_recognition_ineligibility_reasons,
)
from projectkoios.ingestion.models import (
    ExtractedDocument,
    ExtractedPage,
    SourceDocument,
)
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    RegionRenderConfiguration,
    RenderedRegion,
)
from projectkoios.ingestion.pdf.renderer import PageRegionRenderer

from tests.projectkoios.ingestion.integrations.coco.layout.detector_fixture import (  # noqa: E501
    coco_layout_gate_request,
)
from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)


class FixtureEquationRenderer(PageRegionRenderer):
    """Return one exact synthetic PNG for each requested source box."""

    name = "fixture-equation-renderer"
    version = "1"

    def render(
        self,
        source: SourceDocument,
        content: BinaryIO,
        selections: Iterable[PageRegionSelection],
    ) -> tuple[RenderedRegion, ...]:
        if content.read() != b"layout review fixture":
            raise ValueError("fixture source bytes differ")
        regions: list[RenderedRegion] = []
        for selection in selections:
            if selection.bounding_box is None:
                raise ValueError("fixture requires bounded selections")
            x1, y1, x2, y2 = selection.bounding_box
            regions.append(
                RenderedRegion.create(
                    source=source,
                    page_index=selection.page_index,
                    printed_page_label=None,
                    source_bounding_box=selection.bounding_box,
                    effective_source_bounding_box=selection.bounding_box,
                    pixel_to_source_matrix=(
                        x2 - x1,
                        0.0,
                        0.0,
                        y2 - y1,
                        x1,
                        y1,
                    ),
                    page_rotation_degrees=0,
                    selection_was_full_page=False,
                    configuration=RegionRenderConfiguration(),
                    content=fixture_png(),
                    width_pixels=1,
                    height_pixels=1,
                    processor_name=self.name,
                    processor_version=self.version,
                    backend_name="fixture",
                    backend_version="1",
                )
            )
        return tuple(regions)


def fixture_png() -> bytes:
    """Return one valid one-pixel RGB PNG."""

    def chunk(kind: bytes, content: bytes) -> bytes:
        checksum = zlib.crc32(kind + content) & 0xFFFFFFFF
        return (
            len(content).to_bytes(4, "big")
            + kind
            + content
            + checksum.to_bytes(4, "big")
        )

    ihdr = (
        (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes((8, 2, 0, 0, 0))
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )


def equation_projection_request(
    *,
    configuration: CocoLayoutEquationProjectionConfiguration | None = None,
    duplicate_formula: bool = False,
) -> CocoLayoutEquationProjectionRequest:
    """Build one admitted fixture request with exact document lineage."""
    source, page = LayoutReviewFixture().source_page()
    document = ExtractedDocument.create(source=source, pages=(page,))
    gate_request = coco_layout_gate_request(
        include_limitations=True,
        duplicate_formula=duplicate_formula,
    )
    detector_result = gate_request.parsing_result.detector_result
    if detector_result is None:
        raise ValueError("fixture parsing unexpectedly failed")
    admission = CocoLayoutRegionAdmissionActionizer().action(
        request=CocoLayoutRegionAdmissionRequest(
            parsing_result=gate_request.parsing_result,
            proposal_result=gate_request.proposal_result,
            configuration=CocoLayoutRegionAdmissionConfiguration(
                profile=detector_result.request.configuration.profile
            ),
        )
    )
    return CocoLayoutEquationProjectionRequest(
        document=document,
        admission_result=admission,
        configuration=(
            configuration or CocoLayoutEquationProjectionConfiguration()
        ),
    )


def test_projection_maps_admitted_formula_to_source_geometry() -> None:
    request = equation_projection_request()

    result = CocoLayoutEquationProjectionActionizer().action(request=request)

    assert len(result.candidates) == 1
    assert len(result.exclusions) == 0
    candidate = tuple(result.candidates)[0]
    assert candidate.pixel_bounding_box == (20.0, 20.0, 80.0, 40.0)
    assert candidate.mapped_source_bounding_box == (
        10.0,
        10.0,
        40.0,
        20.0,
    )
    assert candidate.source_span.bounding_box == (7.0, 7.0, 43.0, 23.0)
    assert candidate.render.render_id == (
        request.admission_result.request.detector_result.request.render.render_id
    )
    assert candidate.detection_id == candidate.adaptation.detection.detection_id
    assert candidate.adaptation.proposal.confidence == 0.9
    assert result == CocoLayoutEquationProjectionActionizer().action(
        request=request
    )


def test_projection_consumes_generic_duplicate_admission() -> None:
    request = equation_projection_request(duplicate_formula=True)
    result = CocoLayoutEquationProjectionActionizer().action(request=request)

    assert len(result.candidates) == 1
    assert len(result.exclusions) == 0
    assert tuple(
        evidence.disposition for evidence in request.formula_admission.evidence
    ) == (
        CocoLayoutRegionAdmissionDisposition.ADMITTED,
        CocoLayoutRegionAdmissionDisposition.EXCLUDED_DUPLICATE,
    )


def test_projection_rejects_forged_pixel_to_source_mapping() -> None:
    result = CocoLayoutEquationProjectionActionizer().action(
        request=equation_projection_request()
    )
    candidate = tuple(result.candidates)[0]

    with pytest.raises(ValueError, match="source mapping differs"):
        replace(
            candidate,
            mapped_source_bounding_box=(11.0, 10.0, 40.0, 20.0),
        )


def test_pixel_mapping_rejects_out_of_bounds_box() -> None:
    result = CocoLayoutEquationProjectionActionizer().action(
        request=equation_projection_request()
    )
    mapping = tuple(result.candidates)[0].render.mapping

    with pytest.raises(ValueError, match="exceeds mapped image bounds"):
        mapping.pixel_box_to_source_box(
            (0.0, 0.0, float(mapping.image_width + 1), 1.0)
        )


def test_projection_retains_below_threshold_formula_exclusion() -> None:
    request = equation_projection_request(
        configuration=CocoLayoutEquationProjectionConfiguration(
            minimum_confidence=0.95
        )
    )

    result = CocoLayoutEquationProjectionActionizer().action(request=request)

    assert len(result.candidates) == 0
    assert tuple(result.exclusions)[0].code is (
        CocoLayoutEquationExclusionCode.BELOW_CONFIDENCE_THRESHOLD
    )


def test_projection_rejects_nonadmitted_formula_category() -> None:
    source, page = LayoutReviewFixture().source_page()
    gate_request = coco_layout_gate_request(omit_formula=True)
    detector_result = gate_request.parsing_result.detector_result
    if detector_result is None:
        raise ValueError("fixture parsing unexpectedly failed")
    admission = CocoLayoutRegionAdmissionActionizer().action(
        request=CocoLayoutRegionAdmissionRequest(
            parsing_result=gate_request.parsing_result,
            proposal_result=gate_request.proposal_result,
            configuration=CocoLayoutRegionAdmissionConfiguration(
                profile=detector_result.request.configuration.profile
            ),
        )
    )

    with pytest.raises(ValueError, match="admitted formula category"):
        CocoLayoutEquationProjectionRequest(
            document=ExtractedDocument.create(source=source, pages=(page,)),
            admission_result=admission,
            configuration=CocoLayoutEquationProjectionConfiguration(),
        )


def test_projection_rejects_document_lineage_drift() -> None:
    exact = equation_projection_request()
    other_source = SourceDocument.from_bytes(
        b"other",
        source_id="fixture:other",
        media_type="application/pdf",
        locator="fixture://other.pdf",
    )

    other_page = ExtractedPage(
        page_index=0,
        width=100.0,
        height=100.0,
        blocks=(),
        coordinate_system=(exact.document.pages[0].coordinate_system),
    )

    with pytest.raises(ValueError, match="another source"):
        replace(
            exact,
            document=ExtractedDocument.create(
                source=other_source,
                pages=(other_page,),
            ),
        )


def test_assembler_produces_primary_recognition_ready_evidence() -> None:
    projection = CocoLayoutEquationProjectionActionizer().action(
        request=equation_projection_request()
    )

    result = CocoLayoutEquationAssembler(
        renderer=FixtureEquationRenderer()
    ).assemble(projection, b"layout review fixture")

    assert len(result.assemblies) == 1
    assembly = result.assemblies[0]
    assert assembly.detection_result_id == projection.result_id
    assert assembly.source_block_ids == ()
    assert assembly.sanitized_native_text == ""
    assert assembly.prefilter_reasons == (
        "layout_detector_without_native_text",
    )
    assert primary_equation_recognition_ineligibility_reasons(assembly) == ()
    pix2tex_reasons = pix2tex_primary_recognition_ineligibility_reasons(
        assembly
    )
    assert "native_text_length_outside_4_64" not in pix2tex_reasons
    assert assembly.rendered_region.source_bounding_box == (
        7.0,
        7.0,
        43.0,
        23.0,
    )


def test_assembler_rejects_source_byte_drift() -> None:
    projection = CocoLayoutEquationProjectionActionizer().action(
        request=equation_projection_request()
    )

    with pytest.raises(ValueError, match="requires exact PDF bytes"):
        CocoLayoutEquationAssembler(
            renderer=FixtureEquationRenderer()
        ).assemble(projection, b"drift")
