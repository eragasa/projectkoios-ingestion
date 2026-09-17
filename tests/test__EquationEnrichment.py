from __future__ import annotations

import hashlib
import json
import shutil
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
    Pix2TexCliEquationRecognizer,
    PyMuPdfExtractor,
    SourceDocument,
    build_equation_index,
)
from projectkoios.ingestion.batch_cli import main as ingest_batch
from projectkoios.ingestion.equation_batch_cli import main as equation_batch
from projectkoios.ingestion.equation_enrichment import _sanitize_native_text
from projectkoios.ingestion.equation_enrichment_cli import main as enrich_batch

pytest.importorskip("pymupdf")
FIXTURES = Path(__file__).parent / "fixtures" / "pdf"


def _detection():
    payload = (FIXTURES / "equations.pdf").read_bytes()
    source = SourceDocument.from_bytes(
        payload,
        source_id="article:equation:enrichment",
        media_type="application/pdf",
        locator="assets/equations.pdf",
    )
    extraction = PyMuPdfExtractor().extract(source, BytesIO(payload))
    detection = DeterministicEquationCandidateDetector().detect(
        extraction.document, BytesIO(payload)
    )
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
        resources=(("model", model),),
    )


def test__equation_enrichment__keeps_raw_sanitized_and_visual_layers(
    tmp_path: Path,
) -> None:
    payload, detection = _detection()

    assembly = DeterministicEquationAssembler().assemble(detection, payload)
    recognition = _recognizer(tmp_path).process(assembly)
    index = build_equation_index(assembly, recognition)

    assert len(assembly.assemblies) == 1
    assembled = assembly.assemblies[0]
    assert assembled.raw_fragments == ("E = m c^2    (1)",)
    assert assembled.sanitized_native_text == "E = m c^2 (1)"
    assert assembled.rendered_region.content.startswith(b"\x89PNG\r\n\x1a\n")
    proposal = recognition.proposals[0]
    assert proposal.status is EquationRecognitionStatus.PROPOSED
    assert proposal.latex == r"E=mc^2"
    assert proposal.mathml is not None
    assert "recognition_confidence_unavailable" in proposal.warning_codes
    record = index.records[0]
    assert record.tier is EquationIndexTier.PRIMARY
    assert record.raw_fragments == assembled.raw_fragments
    assert record.sanitized_native_text == assembled.sanitized_native_text
    assert record.latex_proposal == proposal.latex
    assert record.mathml_proposal == proposal.mathml
    assert "Unaccepted LaTeX proposal" in record.retrieval_text


def test__equation_enrichment__malformed_latex_remains_auxiliary(
    tmp_path: Path,
) -> None:
    payload, detection = _detection()
    assembly = DeterministicEquationAssembler().assemble(detection, payload)

    recognition = _recognizer(tmp_path, latex=r"\frac{x{").process(assembly)
    index = build_equation_index(assembly, recognition)

    assert "latex_structure_suspect" in recognition.proposals[0].warning_codes
    assert index.records[0].tier is EquationIndexTier.AUXILIARY
    assert "latex_structure_suspect" in index.records[0].reasons


def test__equation_enrichment__keeps_prose_like_latex_auxiliary(
    tmp_path: Path,
) -> None:
    payload, detection = _detection()
    assembly = DeterministicEquationAssembler().assemble(detection, payload)

    recognition = _recognizer(
        tmp_path, latex=r"\mathrm{largest~eigenvalue}"
    ).process(assembly)
    index = build_equation_index(assembly, recognition)

    assert index.records[0].tier is EquationIndexTier.AUXILIARY
    assert "latex_prose_suspect" in index.records[0].reasons


def test__equation_enrichment__sanitizes_without_erasing_raw_evidence() -> None:
    raw = "x\x08 = y\n+ z"

    sanitized, count = _sanitize_native_text(raw)

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
                sha256=hashlib.sha256(payload).hexdigest(),
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
    assert enrich_batch([*arguments, "--apply"]) == 0
    replayed = json.loads(capsys.readouterr().out)
    assert replayed["items"][0]["action"] == "unchanged"
    derived = ingestion / "article/derived/equations"
    assert (derived / "assembly.json").is_file()
    assert (derived / "recognition.json").is_file()
    assert (derived / "index.json").is_file()


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
        resources=(("model", model),),
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
        resources=(("model", model),),
    )

    payload, detection = _detection()
    assembly = DeterministicEquationAssembler().assemble(detection, payload)
    with pytest.raises(ValueError, match="resource changed"):
        first.process(assembly)

    assert before != second.identity.identity_digest
    assert (
        second.identity.resources[0].sha256
        == hashlib.sha256(b"changed model identity").hexdigest()
    )
