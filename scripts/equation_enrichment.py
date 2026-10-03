from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from projectkoios.ingestion.batch import PdfBatchPlan
from projectkoios.ingestion.cache import _require_bounded_json_nesting
from projectkoios.ingestion.cli import (
    ArtifactPublicationError,
    ExtractionCacheOperationError,
    _publish_artifacts,
)
from projectkoios.ingestion.equation_batch_cli import (
    _derive,
    _resolve_items,
    _ResolvedItem,
)
from projectkoios.ingestion.equations.assembly.assembler import (
    DeterministicEquationAssembler,
)
from projectkoios.ingestion.equations.derivation.recognition.record import (
    EquationRecognitionDerivationRecord,
)
from projectkoios.ingestion.equations.index.builder import build_equation_index
from projectkoios.ingestion.equations.index.tier import EquationIndexTier
from projectkoios.ingestion.equations.publication.member import (
    EquationPublicationMember,
    EquationPublicationMemberName,
)
from projectkoios.ingestion.equations.publication.request import (
    EquationPublicationRequest,
)
from projectkoios.ingestion.equations.publication.status import (
    EquationPublicationInventoryStatus,
)
from projectkoios.ingestion.equations.recognition.error import (
    EquationRecognitionError,
)
from projectkoios.ingestion.equations.recognition.identity import (
    equation_recognition_request_id,
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
from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.storage.artifact import ArtifactPublicationItem

from workflow.equation_recognition import (
    execute_equation_recognition_derivation,
)


class _EnrichmentTarget:
    def __init__(self, ingestion_directory: Path) -> None:
        root = ingestion_directory / "derived" / "equations"
        self.assembly = root / "assembly.json"
        self.recognition = root / "recognition.json"
        self.index = root / "index.json"
        self.derivation = root / "derivation.json"
        assembly_exists = os.path.lexists(self.assembly)
        recognition_exists = os.path.lexists(self.recognition)
        index_exists = os.path.lexists(self.index)
        derivation_exists = os.path.lexists(self.derivation)
        core_exists = assembly_exists and recognition_exists and index_exists
        core_partially_exists = (
            assembly_exists or recognition_exists or index_exists
        ) and not core_exists
        if core_partially_exists:
            raise ValueError("equation enrichment artifact set is incomplete")
        if derivation_exists and not core_exists:
            raise ValueError("equation derivation exists without core evidence")
        if core_exists and (
            self._unsafe(self.assembly)
            or self._unsafe(self.recognition)
            or self._unsafe(self.index)
            or (derivation_exists and self._unsafe(self.derivation))
        ):
            raise ValueError(
                "equation enrichment artifacts are not safe regular files"
            )
        self.existing = core_exists
        self.derivation_present = derivation_exists

    def publication_request(
        self,
        *,
        assembly_content: str,
        recognition_content: str,
        index_content: str,
        derivation_content: str,
    ) -> EquationPublicationRequest:
        return EquationPublicationRequest(
            assembly=EquationPublicationMember(
                name=EquationPublicationMemberName.ASSEMBLY,
                path=self.assembly,
                content=assembly_content,
            ),
            recognition=EquationPublicationMember(
                name=EquationPublicationMemberName.RECOGNITION,
                path=self.recognition,
                content=recognition_content,
            ),
            index=EquationPublicationMember(
                name=EquationPublicationMemberName.INDEX,
                path=self.index,
                content=index_content,
            ),
            derivation=EquationPublicationMember(
                name=EquationPublicationMemberName.DERIVATION,
                path=self.derivation,
                content=derivation_content,
            ),
        )

    @staticmethod
    def _unsafe(path: Path) -> bool:
        return path.is_symlink() or not path.is_file()


@dataclass(frozen=True)
class _EnrichmentWorkItem:
    source: _ResolvedItem
    target: _EnrichmentTarget


def _publish_equation_request(
    request: EquationPublicationRequest,
) -> None:
    _publish_artifacts(
        [
            ArtifactPublicationItem(
                path=request.assembly.path,
                text=request.assembly.content,
            ),
            ArtifactPublicationItem(
                path=request.recognition.path,
                text=request.recognition.content,
            ),
            ArtifactPublicationItem(
                path=request.index.path,
                text=request.index.content,
            ),
            ArtifactPublicationItem(
                path=request.derivation.path,
                text=request.derivation.content,
            ),
        ]
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.equation_enrichment"
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ingestion-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--low-text-threshold", type=int, default=40)
    parser.add_argument("--pix2tex-executable", type=Path, required=True)
    parser.add_argument("--pix2tex-backend-version", required=True)
    parser.add_argument(
        "--pix2tex-resource",
        action="append",
        default=[],
        metavar="NAME=PATH",
    )
    parser.add_argument("--pix2tex-temperature", type=float, default=0.01)
    parser.add_argument("--pix2tex-timeout", type=int, default=900)
    parser.add_argument("--apply", action="store_true")
    return parser


def _resources(values: list[str]) -> tuple[Pix2TexResourceBinding, ...]:
    resources: list[Pix2TexResourceBinding] = []
    for value in values:
        name, separator, raw_path = value.partition("=")
        if not separator or not name or not raw_path:
            raise ValueError("pix2tex resources must use NAME=PATH")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]*", name):
            raise ValueError("pix2tex resource names must be portable")
        path = Path(raw_path).expanduser().resolve()
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"pix2tex resource is not a safe file: {name}")
        resources.append(Pix2TexResourceBinding(name=name, path=path))
    names = tuple(resource.name for resource in resources)
    if not names or len(names) != len(set(names)):
        raise ValueError("pix2tex resources must be non-empty and unique")
    return tuple(resources)


def _load_bounded_json(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    if len(content) > 128_000_000:
        raise ValueError("equation enrichment artifact exceeds the size limit")
    text = content.decode("utf-8", errors="strict")
    _require_bounded_json_nesting(text)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("equation enrichment artifact must be an object")
    return value


def _existing_summary(
    *,
    source_id: str,
    output_directory: str,
    candidate_count: int,
    assembly_artifact_id: str,
    assembly_count: int,
    target: _EnrichmentTarget,
    processor_identity_digest: str,
) -> dict[str, object]:
    recognition = _load_bounded_json(target.recognition)
    index = _load_bounded_json(target.index)
    derivation = (
        _load_bounded_json(target.derivation)
        if target.derivation_present
        else None
    )
    proposals = recognition.get("proposals")
    records = index.get("records")
    if not isinstance(proposals, list) or not isinstance(records, list):
        raise ValueError("existing equation enrichment has an invalid shape")
    if recognition.get("assembly_artifact_id") != assembly_artifact_id:
        raise ValueError("existing recognition does not match assembly replay")
    if any(
        not isinstance(proposal, dict)
        or proposal.get("processor_identity_digest")
        != processor_identity_digest
        for proposal in proposals
    ):
        raise ValueError("existing recognition processor identity changed")
    recognition_artifact_id = recognition.get("artifact_id")
    index_artifact_id = index.get("artifact_id")
    expected_request_id = equation_recognition_request_id(
        assembly_artifact_id,
        processor_identity_digest,
    )
    if (
        not isinstance(recognition_artifact_id, str)
        or not isinstance(index_artifact_id, str)
        or index.get("assembly_artifact_id") != assembly_artifact_id
        or index.get("recognition_artifact_id") != recognition_artifact_id
        or index.get("source_id") != source_id
    ):
        raise ValueError("existing equation index linkage is inconsistent")
    derivation_record: EquationRecognitionDerivationRecord | None = None
    if derivation is not None:
        try:
            derivation_record = EquationRecognitionDerivationRecord.from_dict(
                derivation
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                "existing equation derivation linkage is inconsistent"
            ) from error
        if (
            derivation_record.request_id != expected_request_id
            or derivation_record.recognition_artifact_id
            != recognition_artifact_id
        ):
            raise ValueError(
                "existing equation derivation linkage is inconsistent"
            )
    tiers = {tier.value: 0 for tier in EquationIndexTier}
    for record in records:
        if not isinstance(record, dict) or record.get("tier") not in tiers:
            raise ValueError("existing equation index record is invalid")
        tiers[record["tier"]] += 1
    return {
        "source_id": source_id,
        "output_directory": output_directory,
        "action": "unchanged",
        "candidate_count": candidate_count,
        "assembly_count": assembly_count,
        "recognition_proposal_count": sum(
            isinstance(proposal, dict) and proposal.get("latex") is not None
            for proposal in proposals
        ),
        "index_tiers": tiers,
        "assembly_artifact_id": assembly_artifact_id,
        "recognition_artifact_id": recognition_artifact_id,
        "index_artifact_id": index_artifact_id,
        "publication_status": (
            EquationPublicationInventoryStatus.COMPLETE_SET.value
            if derivation is not None
            else EquationPublicationInventoryStatus.LEGACY_PAIR.value
        ),
        "derivation_record_id": (
            derivation_record.record_id
            if derivation_record is not None
            else None
        ),
        "assembly_artifact_sha256": hashlib.sha256(
            target.assembly.read_bytes()
        ).hexdigest(),
        "recognition_artifact_sha256": hashlib.sha256(
            target.recognition.read_bytes()
        ).hexdigest(),
        "index_artifact_sha256": hashlib.sha256(
            target.index.read_bytes()
        ).hexdigest(),
        "derivation_artifact_sha256": (
            hashlib.sha256(target.derivation.read_bytes()).hexdigest()
            if derivation is not None
            else None
        ),
    }


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(arguments)
    try:
        plan = PdfBatchPlan.from_json(args.plan.read_text(encoding="utf-8"))
        resolved = _resolve_items(
            plan,
            source_root=args.source_root,
            ingestion_root=args.ingestion_root,
        )
        if not all(item.existing for item in resolved):
            raise ValueError(
                "equation detection artifacts must exist before enrichment"
            )
        work_items = tuple(
            _EnrichmentWorkItem(
                source=item,
                target=_EnrichmentTarget(item.ingestion_directory),
            )
            for item in resolved
        )
        resources = _resources(args.pix2tex_resource)
        recognizer = Pix2TexCliEquationRecognizer(
            args.pix2tex_executable,
            backend_version=args.pix2tex_backend_version,
            resources=resources,
            temperature=args.pix2tex_temperature,
            timeout_seconds=args.pix2tex_timeout,
        )
    except (OSError, ValueError) as error:
        parser.error(f"invalid equation enrichment plan: {error}")

    if not args.apply:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "planned",
                    "processor_identity": recognizer.identity.identity_digest,
                    "items": [
                        {
                            "source_id": work_item.source.item.source_id,
                            "output_directory": (
                                work_item.source.item.output_directory.as_posix()
                            ),
                            "action": (
                                "verify_existing"
                                if work_item.target.existing
                                else "create"
                            ),
                        }
                        for work_item in work_items
                    ],
                },
                indent=2,
            )
        )
        return 2

    completed: list[dict[str, object]] = []
    try:
        for work_item in work_items:
            item = work_item.source
            target = work_item.target
            detection, _, _ = _derive(
                item,
                cache_root=args.cache_root,
                low_text_threshold=args.low_text_threshold,
            )
            payload = item.pdf.read_bytes()
            if hashlib.sha256(payload).hexdigest() != item.item.sha256:
                raise ValueError(
                    "PDF source changed after enrichment preflight"
                )
            assembly = DeterministicEquationAssembler(
                renderer=PyMuPdfRegionRenderer()
            ).assemble(detection, payload)
            assembly_text = serialize_contract(assembly) + "\n"
            if target.existing:
                if target.assembly.read_text(encoding="utf-8") != assembly_text:
                    raise ValueError(
                        "existing equation assembly differs from replay"
                    )
                completed.append(
                    _existing_summary(
                        source_id=item.item.source_id,
                        output_directory=(
                            item.item.output_directory.as_posix()
                        ),
                        candidate_count=len(detection.candidates),
                        assembly_artifact_id=assembly.artifact_id,
                        assembly_count=len(assembly.assemblies),
                        target=target,
                        processor_identity_digest=(
                            recognizer.identity.identity_digest
                        ),
                    )
                )
                continue
            derivation_result = execute_equation_recognition_derivation(
                recognizer=recognizer,
                assembly=assembly,
            )
            recognition = derivation_result.recognition
            derivation = EquationRecognitionDerivationRecord.create(
                derivation_result
            )
            index = build_equation_index(assembly, recognition)
            publication = target.publication_request(
                assembly_content=assembly_text,
                recognition_content=serialize_contract(recognition) + "\n",
                index_content=serialize_contract(index) + "\n",
                derivation_content=serialize_contract(derivation) + "\n",
            )
            parent = target.assembly.parent
            if parent.resolve() != parent:
                raise ValueError(
                    "equation enrichment path changed after planning"
                )
            _publish_equation_request(publication)
            tiers = {
                tier.value: sum(record.tier is tier for record in index.records)
                for tier in EquationIndexTier
            }
            completed.append(
                {
                    "source_id": item.item.source_id,
                    "output_directory": item.item.output_directory.as_posix(),
                    "action": "created",
                    "candidate_count": len(detection.candidates),
                    "assembly_count": len(assembly.assemblies),
                    "recognition_proposal_count": sum(
                        proposal.latex is not None
                        for proposal in recognition.proposals
                    ),
                    "index_tiers": tiers,
                    "assembly_artifact_id": assembly.artifact_id,
                    "recognition_artifact_id": recognition.artifact_id,
                    "index_artifact_id": index.artifact_id,
                    "publication_status": (
                        EquationPublicationInventoryStatus.COMPLETE_SET.value
                    ),
                    "derivation_record_id": derivation.record_id,
                    "assembly_artifact_sha256": hashlib.sha256(
                        target.assembly.read_bytes()
                    ).hexdigest(),
                    "recognition_artifact_sha256": hashlib.sha256(
                        target.recognition.read_bytes()
                    ).hexdigest(),
                    "index_artifact_sha256": hashlib.sha256(
                        target.index.read_bytes()
                    ).hexdigest(),
                    "derivation_artifact_sha256": hashlib.sha256(
                        target.derivation.read_bytes()
                    ).hexdigest(),
                }
            )
    except EquationRecognitionError as error:
        parser.error(
            "equation-recognition transition failed after "
            f"{len(completed)} completed items: {error}"
        )
    except (
        ArtifactPublicationError,
        ExtractionCacheOperationError,
        OSError,
        ValueError,
    ) as error:
        parser.error(
            "equation enrichment stopped after "
            f"{len(completed)} completed items: {error}"
        )
    print(
        json.dumps(
            {
                "schema_version": 1,
                "status": "completed",
                "processor_identity": recognizer.identity.identity_digest,
                "items": completed,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
