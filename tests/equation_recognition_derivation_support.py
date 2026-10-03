from __future__ import annotations

import hashlib
import zlib

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
from projectkoios.ingestion.equations.image.factory import EquationImage
from projectkoios.ingestion.equations.latex import EquationLatex
from projectkoios.ingestion.equations.mathml import EquationMathML
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.identity import (
    EQUATION_RECOGNITION_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.recognition.processor.identity import (
    EquationRecognitionProcessorIdentity,
)
from projectkoios.ingestion.equations.recognition.proposal import (
    EquationRecognitionProposal,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from projectkoios.ingestion.equations.recognition.resource import (
    EquationRecognitionResource,
)
from projectkoios.ingestion.equations.recognition.status import (
    EquationRecognitionStatus,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.pdf.models import (
    RegionRenderConfiguration,
    RenderedRegion,
)


def assembly(*, name: str = "fixture") -> EquationAssemblyResult:
    source_content = f"source:{name}".encode()
    source = SourceDocument.from_bytes(
        source_content,
        source_id=f"source:{name}",
        media_type="application/pdf",
        locator=f"fixtures/{name}.pdf",
    )
    region = RenderedRegion.create(
        source=source,
        page_index=0,
        printed_page_label="1",
        source_bounding_box=(0.0, 0.0, 1.0, 1.0),
        effective_source_bounding_box=(0.0, 0.0, 1.0, 1.0),
        pixel_to_source_matrix=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        page_rotation_degrees=0,
        selection_was_full_page=False,
        configuration=RegionRenderConfiguration(),
        content=_png(),
        width_pixels=1,
        height_pixels=1,
        processor_name="fixture-renderer",
        processor_version="1",
        backend_name="fixture",
        backend_version="1",
    )
    candidate_ids = (f"candidate:{name}",)
    statuses = (EquationEvidenceStatus.PROPOSED,)
    assembly_id = equation_assembly_id(
        f"detection:{name}",
        candidate_ids,
        statuses,
        region.region_id,
        "x = 1",
        (),
        False,
    )
    equation_assembly = EquationAssembly(
        assembly_id=assembly_id,
        detection_result_id=f"detection:{name}",
        candidate_ids=candidate_ids,
        detector_evidence_statuses=statuses,
        kind=EquationAssemblyKind.DISPLAY,
        page_index=0,
        printed_page_label="1",
        source_spans=(),
        source_block_ids=(f"block:{name}",),
        raw_fragments=("x = 1",),
        sanitized_native_text="x = 1",
        control_character_count=0,
        source_labels=(),
        preceding_context_text=None,
        following_context_text=None,
        rendered_region=region,
        prefilter_reasons=(),
        rejected=False,
    )
    artifact_id = stable_id(
        "equation-assembly-artifact",
        EQUATION_ASSEMBLY_CONTRACT_VERSION,
        source.source_id,
        source.content_hash,
        f"document:{name}",
        f"detection:{name}",
        (assembly_id,),
    )
    return EquationAssemblyResult(
        artifact_id=artifact_id,
        source_id=source.source_id,
        source_content_hash=source.content_hash,
        document_id=f"document:{name}",
        detection_result_id=f"detection:{name}",
        assemblies=(equation_assembly,),
    )


def processor(*, name: str = "fixture") -> EquationRecognitionProcessorIdentity:
    return EquationRecognitionProcessorIdentity(
        processor_name="bounded-recognizer",
        processor_version="1",
        backend_name="test",
        backend_version="1",
        executable_sha256="a" * 64,
        executable_semantic_sha256="b" * 64,
        resources=(
            EquationRecognitionResource(
                name="model",
                path=f"/bounded/{name}/model",
                sha256="c" * 64,
                byte_size=1,
            ),
        ),
        temperature=0.01,
    )


def request(*, name: str = "fixture") -> EquationRecognitionRequest:
    return EquationRecognitionRequest.create(
        assembly_artifact=assembly(name=name),
        processor_identity=processor(name=name),
    )


def artifact(
    *,
    recognition_request: EquationRecognitionRequest | None = None,
    name: str = "fixture",
) -> EquationRecognitionArtifact:
    actual_request = recognition_request or request(name=name)
    proposals = tuple(
        _proposal(
            equation_assembly=equation_assembly,
            processor_identity_digest=(
                actual_request.processor_identity.identity_digest
            ),
        )
        for equation_assembly in actual_request.assembly_artifact.assemblies
    )
    diagnostic_sha256 = hashlib.sha256(b"").hexdigest()
    artifact_id = stable_id(
        "equation-recognition-artifact",
        EQUATION_RECOGNITION_CONTRACT_VERSION,
        actual_request.assembly_artifact.artifact_id,
        actual_request.processor_identity.identity_digest,
        tuple(proposal.proposal_id for proposal in proposals),
        0,
        0,
        diagnostic_sha256,
    )
    return EquationRecognitionArtifact(
        artifact_id=artifact_id,
        assembly_artifact_id=actual_request.assembly_artifact.artifact_id,
        processor_identity=actual_request.processor_identity,
        proposals=proposals,
        invocation_exit_code=0,
        diagnostic_byte_size=0,
        diagnostic_sha256=diagnostic_sha256,
    )


def _proposal(
    *,
    equation_assembly: EquationAssembly,
    processor_identity_digest: str,
) -> EquationRecognitionProposal:
    image = EquationImage.from_bytes(
        content=equation_assembly.rendered_region.content,
        source_ids=(equation_assembly.rendered_region.region_id,),
    )
    latex = EquationLatex(
        source_ids=(image.equation_id,),
        latex="x = 1",
    )
    mathml = EquationMathML(
        source_ids=(latex.equation_id,),
        mathml="<math><mi>x</mi><mo>=</mo><mn>1</mn></math>",
    )
    proposal_id = stable_id(
        "equation-recognition-proposal",
        EQUATION_RECOGNITION_CONTRACT_VERSION,
        equation_assembly.assembly_id,
        EquationRecognitionStatus.PROPOSED,
        latex.latex,
        mathml.mathml,
        (),
        None,
        processor_identity_digest,
    )
    return EquationRecognitionProposal(
        proposal_id=proposal_id,
        assembly_id=equation_assembly.assembly_id,
        status=EquationRecognitionStatus.PROPOSED,
        latex=latex,
        mathml=mathml,
        mathml_processor_identity=stable_id(
            "equation-mathml-processor",
            "fixture",
            "1",
        ),
        mathml_processor_version="1",
        warning_codes=(),
        failure_message=None,
        processor_identity_digest=processor_identity_digest,
    )


def _png() -> bytes:
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
