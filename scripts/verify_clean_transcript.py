#!/usr/bin/env python3
"""Offline verifier for the committed canonical clean-transcript source.

Inputs: one repository root and one committed PDF fixture within that root.
Effects: reads Git metadata/source/fixture bytes and writes one JSON summary to
stdout; it does not write repository or cache files and performs no network I/O.
Stops: uncommitted verifier inputs, unsafe/untracked/oversized fixtures, imports
outside the selected source tree, nondeterministic projection/serialization, a
legacy top-level format key, or a failing transitive derivation audit.
Limits: one PDF, at most 16 MiB; normal ingestion object/page limits also apply.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from io import BytesIO
from pathlib import Path

_MAX_FIXTURE_BYTES = 16 * 1024 * 1024
_VERIFIER_INPUTS = (
    "scripts/verify_clean_transcript.py",
    "src/python/projectkoios/ingestion/clean_transcript.py",
    "src/python/projectkoios/ingestion/transcript_batch.py",
    "src/python/projectkoios/ingestion/provenance/audit.py",
    "src/python/projectkoios/ingestion/provenance/domains.py",
    "src/python/projectkoios/ingestion/reference_evidence.py",
    "src/python/projectkoios/ingestion/reference_locator.py",
)
_REMOVED_TOP_LEVEL_KEYS = frozenset(
    {
        "artifact_generation",
        "contract_id",
        "contract_version",
        "schema_version",
    }
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verify-clean-transcript")
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/pdf/equations.pdf"),
    )
    return parser


def _git(
    root: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", "-C", str(root), *arguments),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _require_committed_inputs(root: Path, fixture: Path) -> None:
    relative_fixture = fixture.relative_to(root).as_posix()
    paths = (*_VERIFIER_INPUTS, relative_fixture)
    tracked = _git(root, "ls-files", "--error-unmatch", "--", *paths)
    if tracked.returncode != 0:
        raise ValueError("verifier inputs must all be tracked")
    changed = _git(root, "diff", "--quiet", "HEAD", "--", *paths)
    if changed.returncode != 0:
        raise ValueError("verifier inputs must match committed HEAD")


def _require_fixture(root: Path, value: Path) -> Path:
    fixture = (root / value).absolute() if not value.is_absolute() else value
    fixture = fixture.resolve()
    if not fixture.is_relative_to(root):
        raise ValueError("fixture must remain within the repository")
    if fixture.is_symlink() or not fixture.is_file():
        raise ValueError("fixture must be a safe regular file")
    size = fixture.stat().st_size
    if size <= 0 or size > _MAX_FIXTURE_BYTES:
        raise ValueError("fixture exceeds the bounded size policy")
    return fixture


def _verify(root: Path, fixture: Path) -> dict[str, object]:
    import projectkoios.ingestion.clean_transcript as clean_module
    from projectkoios.ingestion.article_structure import (
        DeterministicArticleStructureAnalyzer,
    )
    from projectkoios.ingestion.clean_transcript import (
        CleanTranscriptRequest,
        DeterministicCleanTranscriptProjector,
    )
    from projectkoios.ingestion.equations.detection import (
        DeterministicEquationCandidateDetector,
    )
    from projectkoios.ingestion.figures import (
        DeterministicFigureCandidateDetector,
    )
    from projectkoios.ingestion.layout import DeterministicLayoutProcessor
    from projectkoios.ingestion.models import SourceDocument
    from projectkoios.ingestion.pdf import PyMuPdfExtractor
    from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
        PyMuPdfRegionRenderer,
    )
    from projectkoios.ingestion.provenance import (
        DerivationAuditInput,
        DerivationAuditValidator,
    )
    from projectkoios.ingestion.serialization import serialize_contract
    from projectkoios.ingestion.tables import (
        DeterministicTableCandidateDetector,
    )
    from projectkoios.ingestion.tables.structure.reconstructor import (
        DeterministicTableStructureReconstructor,
    )
    from projectkoios.ingestion.transcription.composition.composer import (
        DeterministicStructuredTranscriptionComposer,
    )
    from projectkoios.ingestion.transcription.request.request import (
        StructuredTranscriptionRequest,
    )

    expected_source = root / "src/python"
    imported_source = Path(clean_module.__file__).resolve()
    if not imported_source.is_relative_to(expected_source):
        raise ValueError(
            "clean-transcript import is not bound to repository source"
        )

    payload = fixture.read_bytes()
    source = SourceDocument.from_bytes(
        payload,
        source_id=f"fixture:clean-transcript:{hashlib.sha256(payload).hexdigest()}",
        media_type="application/pdf",
        locator=fixture.relative_to(root).as_posix(),
    )
    extraction = PyMuPdfExtractor().extract(source, BytesIO(payload))
    document = extraction.document
    layouts = DeterministicLayoutProcessor().analyze(document)
    structure = DeterministicArticleStructureAnalyzer().analyze(document)
    renderer = PyMuPdfRegionRenderer()
    equations = DeterministicEquationCandidateDetector(
        region_renderer=renderer
    ).detect_with_layout(document, BytesIO(payload), layouts)
    table_detection = DeterministicTableCandidateDetector(
        region_renderer=renderer
    ).detect_with_layout(document, BytesIO(payload), layouts)
    tables = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    figures = DeterministicFigureCandidateDetector(
        region_renderer=renderer
    ).detect_with_layout(document, BytesIO(payload), layouts)
    transcription = DeterministicStructuredTranscriptionComposer().action(
        request=StructuredTranscriptionRequest.create(
            document=document,
            structure_analysis=structure,
            equation_detection_result=equations,
            table_structure_result=tables,
            figure_detection_result=figures,
        )
    )
    projector = DeterministicCleanTranscriptProjector()
    request = CleanTranscriptRequest.create(
        transcription_result=transcription,
        layouts=layouts,
        configuration=projector.configuration,
    )
    first = projector.action(request=request)
    second = projector.action(request=request)
    if first != second:
        raise ValueError("clean-transcript projection is nondeterministic")
    first_json = serialize_contract(first) + "\n"
    second_json = serialize_contract(second) + "\n"
    if first_json.encode("utf-8") != second_json.encode("utf-8"):
        raise ValueError("clean-transcript serialization is nondeterministic")
    serialized = json.loads(first_json)
    removed = _REMOVED_TOP_LEVEL_KEYS.intersection(serialized)
    if removed:
        raise ValueError(
            f"clean transcript contains removed keys: {sorted(removed)}"
        )

    audit = DerivationAuditValidator().audit(
        DerivationAuditInput(
            source_content=payload,
            extraction_result=extraction,
            layout_results=layouts,
            structure_analyses=(structure,),
            equation_results=(equations,),
            table_detection_results=(table_detection,),
            table_structure_results=(tables,),
            figure_results=(figures,),
            transcription_results=(transcription,),
            clean_transcripts=(first,),
        )
    )
    audit.require_valid()
    return {
        "audit_report_id": audit.report_id,
        "clean_transcript_result_id": first.result_id,
        "clean_transcript_sha256": hashlib.sha256(
            first_json.encode("utf-8")
        ).hexdigest(),
        "clean_text_sha256": first.text_sha256,
        "fixture": fixture.relative_to(root).as_posix(),
        "fixture_sha256": hashlib.sha256(payload).hexdigest(),
        "request_id": request.request_id,
        "status": "verified",
    }


def main(arguments: list[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    root = args.repository_root.expanduser().resolve()
    if (
        not (root / ".git").exists()
        and not _git(root, "rev-parse", "--git-dir").stdout.strip()
    ):
        raise SystemExit("repository root is not a Git worktree")
    fixture = _require_fixture(root, args.fixture)
    _require_committed_inputs(root, fixture)
    print(json.dumps(_verify(root, fixture), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
