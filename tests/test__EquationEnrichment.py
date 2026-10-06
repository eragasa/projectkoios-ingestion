from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from io import BytesIO
from pathlib import Path, PurePosixPath

import pytest
from projectkoios.ingestion import (
    DeterministicEquationAssembler,
    DeterministicEquationCandidateDetector,
    EquationIndexTier,
    EquationRecognitionStatus,
    PdfBatchItem,
    PdfBatchPlan,
    PyMuPdfExtractor,
    SourceDocument,
    build_equation_index,
)
from projectkoios.ingestion.batch_cli import main as ingest_batch
from projectkoios.ingestion.equation_batch_cli import main as equation_batch
from projectkoios.ingestion.equations.assembly.text import (
    sanitize_equation_native_text,
)
from projectkoios.ingestion.equations.derivation.recognition.operation import (
    EquationRecognitionDerivationOperation,
)
from projectkoios.ingestion.equations.latex import EquationLatex
from projectkoios.ingestion.equations.mathml import EquationMathML
from projectkoios.ingestion.equations.publication.status import (
    EquationPublicationInventoryStatus,
)
from projectkoios.ingestion.equations.recognition.error import (
    EquationRecognitionError,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from projectkoios.ingestion.integrations.pix2tex.recognizer import (
    Pix2TexCliEquationRecognizer,
)
from projectkoios.ingestion.integrations.pix2tex.resource import (
    Pix2TexResourceBinding,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.verifier import SHA256Verifier

pytest.importorskip("pymupdf")
FIXTURES = Path(__file__).parent / "fixtures" / "pdf"
_SCRIPT = Path(__file__).parents[1] / "scripts/equation_enrichment.py"
_SPEC = importlib.util.spec_from_file_location(
    "projectkoios_ingestion_equation_enrichment_script",
    _SCRIPT,
)
assert _SPEC is not None and _SPEC.loader is not None
_SCRIPT_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _SCRIPT_MODULE
_SPEC.loader.exec_module(_SCRIPT_MODULE)
enrich_batch = _SCRIPT_MODULE.main


def _detection():
    payload = (FIXTURES / "equations.pdf").read_bytes()
    source = SourceDocument.from_bytes(
        payload,
        source_id="article:equation:enrichment",
        media_type="application/pdf",
        locator="assets/equations.pdf",
    )
    extraction = PyMuPdfExtractor().extract(source, BytesIO(payload))
    detection = DeterministicEquationCandidateDetector(
        region_renderer=PyMuPdfRegionRenderer()
    ).detect(extraction.document, BytesIO(payload))
    return payload, detection


def _recognizer(tmp_path: Path, latex: str = r"E=mc^2"):
    executable = tmp_path / "fake-pix2tex"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"latex = {latex!r}\n"
        "for value in sys.argv[1:]:\n"
        "    if value.endswith('.png'):\n"
        "        print(f'{pathlib.Path(value).resolve()}: {latex}')\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    model = tmp_path / "model.pth"
    model.write_bytes(b"bounded synthetic model identity")
    return Pix2TexCliEquationRecognizer(
        executable,
        backend_version="test-1",
        resources=(Pix2TexResourceBinding(name="model", path=model),),
    )


def _recognize(recognizer, assembly):
    request = EquationRecognitionRequest.create(
        assembly_artifact=assembly,
        processor_identity=recognizer.identity,
    )
    return recognizer.action(request=request)


def test__equation_enrichment__keeps_raw_sanitized_and_visual_layers(
    tmp_path: Path,
) -> None:
    payload, detection = _detection()

    assembly = DeterministicEquationAssembler(
        renderer=PyMuPdfRegionRenderer()
    ).assemble(detection, payload)
    recognition = _recognize(_recognizer(tmp_path), assembly)
    index = build_equation_index(assembly, recognition)

    assert len(assembly.assemblies) == 1
    assembled = assembly.assemblies[0]
    assert assembled.raw_fragments == ("E = m c^2    (1)",)
    assert assembled.sanitized_native_text == "E = m c^2 (1)"
    assert assembled.rendered_region.content.startswith(b"\x89PNG\r\n\x1a\n")
    proposal = recognition.proposals[0]
    assert proposal.status is EquationRecognitionStatus.PROPOSED
    assert isinstance(proposal.latex, EquationLatex)
    assert proposal.latex.latex == r"E=mc^2"
    assert proposal.latex.equation_source_ids[0].startswith(
        "equation-image:sha256:"
    )
    assert isinstance(proposal.mathml, EquationMathML)
    assert proposal.mathml.equation_source_ids == (proposal.latex.equation_id,)
    assert proposal.mathml_processor_identity is not None
    assert proposal.mathml_processor_version is not None
    assert "recognition_confidence_unavailable" in proposal.warning_codes
    record = index.records[0]
    assert record.tier is EquationIndexTier.PRIMARY
    assert record.raw_fragments == assembled.raw_fragments
    assert record.sanitized_native_text == assembled.sanitized_native_text
    assert record.latex_proposal == proposal.latex.latex
    assert record.mathml_proposal == proposal.mathml.mathml
    assert "Unaccepted LaTeX proposal" in record.retrieval_text


def test__equation_enrichment__malformed_latex_remains_auxiliary(
    tmp_path: Path,
) -> None:
    payload, detection = _detection()
    assembly = DeterministicEquationAssembler(
        renderer=PyMuPdfRegionRenderer()
    ).assemble(detection, payload)

    recognition = _recognize(_recognizer(tmp_path, latex=r"\frac{x{"), assembly)
    index = build_equation_index(assembly, recognition)

    assert "latex_structure_suspect" in recognition.proposals[0].warning_codes
    assert index.records[0].tier is EquationIndexTier.AUXILIARY
    assert "latex_structure_suspect" in index.records[0].reasons


def test__equation_enrichment__keeps_prose_like_latex_auxiliary(
    tmp_path: Path,
) -> None:
    payload, detection = _detection()
    assembly = DeterministicEquationAssembler(
        renderer=PyMuPdfRegionRenderer()
    ).assemble(detection, payload)

    recognition = _recognize(
        _recognizer(tmp_path, latex=r"\mathrm{largest~eigenvalue}"),
        assembly,
    )
    index = build_equation_index(assembly, recognition)

    assert index.records[0].tier is EquationIndexTier.AUXILIARY
    assert "latex_prose_suspect" in index.records[0].reasons


def test__equation_enrichment__sanitizes_without_erasing_raw_evidence() -> None:
    raw = "x\x08 = y\n+ z"

    sanitized, count = sanitize_equation_native_text(raw)

    assert raw == "x\x08 = y\n+ z"
    assert sanitized == "x� = y + z"
    assert count == 2


def test__equation_enrichment_batch__plans_applies_and_replays(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = (FIXTURES / "equations.pdf").read_bytes()
    source = tmp_path / "source"
    source.mkdir()
    shutil.copyfile(FIXTURES / "equations.pdf", source / "equations.pdf")
    plan = PdfBatchPlan(
        schema_version=1,
        items=(
            PdfBatchItem(
                source_id="article:equation:enrichment-batch",
                pdf_path=PurePosixPath("equations.pdf"),
                output_directory=PurePosixPath("article"),
                sha256=SHA256Fingerprinter.fingerprint(content=payload),
                byte_size=len(payload),
                locator="assets/equations.pdf",
            ),
        ),
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_json(), encoding="utf-8")
    ingestion = tmp_path / "ingestion"
    raw_arguments = [
        str(plan_path),
        "--source-root",
        str(source),
        "--output-root",
        str(ingestion),
        "--apply",
    ]
    assert ingest_batch(raw_arguments) == 0
    capsys.readouterr()
    equation_arguments = [
        str(plan_path),
        "--source-root",
        str(source),
        "--ingestion-root",
        str(ingestion),
        "--apply",
    ]
    assert equation_batch(equation_arguments) == 0
    capsys.readouterr()
    recognizer = _recognizer(tmp_path)
    resource = tmp_path / "model.pth"
    arguments = [
        str(plan_path),
        "--source-root",
        str(source),
        "--ingestion-root",
        str(ingestion),
        "--pix2tex-executable",
        str(recognizer.executable),
        "--pix2tex-backend-version",
        "test-1",
        "--pix2tex-resource",
        f"model={resource}",
    ]

    assert enrich_batch(arguments) == 2
    planned = json.loads(capsys.readouterr().out)
    assert planned["items"][0]["action"] == "create"
    assert enrich_batch([*arguments, "--apply"]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["items"][0]["action"] == "created"
    assert created["items"][0]["index_tiers"] == {
        "primary": 1,
        "auxiliary": 0,
        "rejected": 0,
    }
    assert created["items"][0]["publication_status"] == (
        EquationPublicationInventoryStatus.COMPLETE_SET.value
    )
    assert enrich_batch([*arguments, "--apply"]) == 0
    replayed = json.loads(capsys.readouterr().out)
    assert replayed["items"][0]["action"] == "unchanged"
    derived = ingestion / "article/derived/equations"
    assert (derived / "assembly.json").is_file()
    assert (derived / "recognition.json").is_file()
    assert (derived / "index.json").is_file()
    assert (derived / "derivation.json").is_file()
    derivation_path = derived / "derivation.json"
    derivation_text = derivation_path.read_text(encoding="utf-8")
    derivation_payload = json.loads(derivation_text)
    assert (
        derivation_payload["recognition_artifact_id"]
        == (created["items"][0]["recognition_artifact_id"])
    )
    assert derivation_payload["trace"]["root_equation_ids"][0].startswith(
        "equation-image:sha256:"
    )
    assert [
        transition["operation_name"]
        for transition in derivation_payload["trace"]["transitions"]
    ] == [
        EquationRecognitionDerivationOperation.RECOGNITION.value,
        EquationRecognitionDerivationOperation.MATHML_CONVERSION.value,
    ]

    derivation_payload["trace"]["transitions"][0]["operation_version"] = (
        "changed"
    )
    derivation_path.write_text(
        json.dumps(derivation_payload),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="2"):
        enrich_batch([*arguments, "--apply"])
    assert "existing equation derivation linkage is inconsistent" in (
        capsys.readouterr().err
    )
    derivation_path.write_text(derivation_text, encoding="utf-8")

    derivation_path.unlink()
    assert enrich_batch([*arguments, "--apply"]) == 0
    legacy_replay = json.loads(capsys.readouterr().out)
    assert legacy_replay["items"][0]["publication_status"] == (
        EquationPublicationInventoryStatus.LEGACY_PAIR.value
    )
    assert legacy_replay["items"][0]["derivation_record_id"] is None


def test__equation_enrichment__resource_identity_changes_with_model(
    tmp_path: Path,
) -> None:
    first = _recognizer(tmp_path)
    model = tmp_path / "model.pth"
    before = first.identity.identity_digest

    relocated = tmp_path / "relocated-pix2tex"
    relocated.write_text(
        (tmp_path / "fake-pix2tex")
        .read_text()
        .replace("#!/usr/bin/env python3", "#!/different/python"),
        encoding="utf-8",
    )
    relocated.chmod(0o755)
    relocated_recognizer = Pix2TexCliEquationRecognizer(
        relocated,
        backend_version="test-1",
        resources=(Pix2TexResourceBinding(name="model", path=model),),
    )
    assert (
        first.identity.executable_sha256
        != relocated_recognizer.identity.executable_sha256
    )
    assert (
        first.identity.executable_semantic_sha256
        == relocated_recognizer.identity.executable_semantic_sha256
    )
    assert before == relocated_recognizer.identity.identity_digest

    model.write_bytes(b"changed model identity")
    second = Pix2TexCliEquationRecognizer(
        tmp_path / "fake-pix2tex",
        backend_version="test-1",
        resources=(Pix2TexResourceBinding(name="model", path=model),),
    )

    payload, detection = _detection()
    assembly = DeterministicEquationAssembler(
        renderer=PyMuPdfRegionRenderer()
    ).assemble(detection, payload)
    with pytest.raises(EquationRecognitionError, match="resource changed"):
        _recognize(first, assembly)

    assert before != second.identity.identity_digest
    assert SHA256Verifier.verify(
        content=b"changed model identity",
        expected=second.identity.resources[0].sha256,
    )
