from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    DeterministicEquationAssembler,
    DeterministicEquationCandidateDetector,
    EquationAssemblyResult,
    EquationEvidenceStatus,
    EquationRecognitionStatus,
    PyMuPdfExtractor,
    SourceDocument,
)
from projectkoios.ingestion.equations.assembly.identity import (
    EQUATION_ASSEMBLY_CONTRACT_VERSION,
    equation_assembly_id,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.pix2tex.recognizer import (
    Pix2TexCliEquationRecognizer,
    _recognition_proposal,
)
from projectkoios.ingestion.integrations.pix2tex.resource import (
    Pix2TexResourceBinding,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)

pytest.importorskip("pymupdf")
FIXTURES = Path(__file__).parents[4] / "fixtures" / "pdf"


def _assembly(payload: bytes) -> EquationAssemblyResult:
    source = SourceDocument.from_bytes(
        payload,
        source_id="article:equation:ambiguous-recognition-gate",
        media_type="application/pdf",
        locator="assets/equations.pdf",
    )
    extraction = PyMuPdfExtractor().extract(source, BytesIO(payload))
    detection = DeterministicEquationCandidateDetector(
        region_renderer=PyMuPdfRegionRenderer()
    ).detect(extraction.document, BytesIO(payload))
    return DeterministicEquationAssembler(
        renderer=PyMuPdfRegionRenderer()
    ).assemble(detection, payload)


def _ambiguous_assembly(payload: bytes) -> EquationAssemblyResult:
    artifact = _assembly(payload)
    original = artifact.assemblies[0]
    statuses = (EquationEvidenceStatus.AMBIGUOUS,) * len(
        original.detector_evidence_statuses
    )
    assembly_id = equation_assembly_id(
        original.detection_result_id,
        original.candidate_ids,
        statuses,
        original.rendered_region.region_id,
        original.sanitized_native_text,
        original.prefilter_reasons,
        original.rejected,
    )
    ambiguous = replace(
        original,
        assembly_id=assembly_id,
        detector_evidence_statuses=statuses,
    )
    artifact_id = stable_id(
        "equation-assembly-artifact",
        EQUATION_ASSEMBLY_CONTRACT_VERSION,
        artifact.source_id,
        artifact.source_content_hash,
        artifact.document_id,
        artifact.detection_result_id,
        (ambiguous.assembly_id,),
    )
    return replace(
        artifact,
        artifact_id=artifact_id,
        assemblies=(ambiguous,),
    )


def test__pix2tex__does_not_run_for_ambiguous_detector_evidence(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "invoked"
    executable = tmp_path / "fake-pix2tex"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('invoked')\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    model = tmp_path / "model.pth"
    model.write_bytes(b"bounded synthetic model identity")
    recognizer = Pix2TexCliEquationRecognizer(
        executable,
        backend_version="test-1",
        resources=(Pix2TexResourceBinding(name="model", path=model),),
    )
    artifact = _ambiguous_assembly((FIXTURES / "equations.pdf").read_bytes())
    request = EquationRecognitionRequest.create(
        assembly_artifact=artifact,
        processor_identity=recognizer.identity,
    )

    result = recognizer.action(request=request)

    assert hash(request)
    assert hash(result)
    assert result.request_id == request.request_id
    assert recognizer.identity.processor_version == "3"
    assert not marker.exists()
    assert len(result.proposals) == 1
    assert result.proposals[0].status is EquationRecognitionStatus.NOT_REQUESTED
    assert result.proposals[0].warning_codes == (
        "recognition_not_requested_for_non_primary_evidence",
    )


def test__pix2tex__discards_stdout_before_parsing_nonzero_exit(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "fake-pix2tex"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stdout.buffer.write(b'\\xffpartial latex')\n"
        "sys.stderr.buffer.write(b'bounded failure')\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    model = tmp_path / "model.pth"
    model.write_bytes(b"bounded synthetic model identity")
    recognizer = Pix2TexCliEquationRecognizer(
        executable,
        backend_version="test-1",
        resources=(Pix2TexResourceBinding(name="model", path=model),),
    )
    artifact = _assembly((FIXTURES / "equations.pdf").read_bytes())
    request = EquationRecognitionRequest.create(
        assembly_artifact=artifact,
        processor_identity=recognizer.identity,
    )

    result = recognizer.action(request=request)

    failed = tuple(
        proposal
        for proposal in result.proposals
        if proposal.status is EquationRecognitionStatus.FAILED
    )
    assert failed
    assert result.invocation_exit_code == 7
    assert result.diagnostic_byte_size == len(b"bounded failure")
    assert all(proposal.latex is None for proposal in result.proposals)
    assert all(
        proposal.warning_codes == ("pix2tex_failed",) for proposal in failed
    )


def test__recognition_failure__drops_partial_latex() -> None:
    artifact = _assembly((FIXTURES / "equations.pdf").read_bytes())
    assembly = next(
        item
        for item in artifact.assemblies
        if all(
            status is EquationEvidenceStatus.PROPOSED
            for status in item.detector_evidence_statuses
        )
    )

    proposal = _recognition_proposal(
        assembly,
        latex=r"E = mc^2",
        exit_code=1,
        processor_identity_digest=stable_id("test-processor", "partial"),
    )

    assert proposal.status is EquationRecognitionStatus.FAILED
    assert proposal.latex is None
    assert proposal.mathml is None
    assert proposal.warning_codes == ("pix2tex_failed",)
    assert proposal.failure_message == (
        "pix2tex exit code 1; no bounded proposal was retained"
    )
