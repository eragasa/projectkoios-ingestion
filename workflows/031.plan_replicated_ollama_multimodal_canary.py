#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from projectkoios.ingestion.integrations.ollama.base import OllamaRequestOptions
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalConfiguration,
    OllamaMultimodalLimits,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.base import (
    OllamaMultimodalRegionProcessor,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

PREPARATION = Path(
    "/Users/eugene/projects/projectkoios/artifacts"
    "/reference-multimodal-preparation-v2"
)
REFERENCES = Path("/Users/eugene/projects/projectkoios/references")
OUTPUT = Path(
    "/Users/eugene/projects/projectkoios/artifacts"
    "/reference-ollama-multimodal-replicated-canary-v1"
)
OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
OLLAMA_VERSION = "0.34.3"
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_DIGEST = (
    "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"
)
REPLICATES_PER_SAMPLE = 2


@dataclass(frozen=True, slots=True)
class SampleSpecification:
    sample_key: str
    evidence_class: str
    book: str
    source_sha256: str
    chunk_number: int
    candidate_id: str
    member_path: str
    expected_sha256: str
    expected_bytes: int
    audit_profile: str
    expected_visible_labels: tuple[str, ...] = ()


SAMPLES = (
    SampleSpecification(
        sample_key="labeled-figure",
        evidence_class="figure",
        book="SzeLee3Ed",
        source_sha256=(
            "539257eb20229bee438dbd628e017bcf8ba6bb6348198ce1e9000cd685d7263e"
        ),
        chunk_number=4,
        candidate_id=(
            "figure-candidate:sha256:"
            "4f2a63c5f3d25ddd4218bec88770998d2221036584f9efcfa3532bcc521a8296"
        ),
        member_path="figures/figure-001.png",
        expected_sha256=(
            "7148b85feda98a752f50418bca793196ff3c7674c223ee5e1c5e0253f8b7d739"
        ),
        expected_bytes=20_272,
        audit_profile="exact_visible_label_multiset",
        expected_visible_labels=("a", "b", "c"),
    ),
    SampleSpecification(
        sample_key="text-heavy-figure",
        evidence_class="figure",
        book="SzeLee3Ed",
        source_sha256=(
            "539257eb20229bee438dbd628e017bcf8ba6bb6348198ce1e9000cd685d7263e"
        ),
        chunk_number=4,
        candidate_id=(
            "figure-candidate:sha256:"
            "2121930a8c780d861bbbf19de0cdb1b8ffc1de768b1832dc8fdb589363c01d10"
        ),
        member_path="figures/figure-003.png",
        expected_sha256=(
            "1039d5abf31ffdd8a478fb2748b01852d936c31574733830cc72c874f1118ad3"
        ),
        expected_bytes=133_940,
        audit_profile="manual_visible_text_and_clipping",
    ),
    SampleSpecification(
        sample_key="structured-table",
        evidence_class="table",
        book="YuCardona4Ed",
        source_sha256=(
            "acfc317504ba1e20a14686c9cbf66b542fb844b4d29b9cc66307598961963f30"
        ),
        chunk_number=6,
        candidate_id=(
            "table-candidate:sha256:"
            "2ba09090b83495ae27bf54c058a9e9666de99ac7325f14cf4cf46db6c431e3fd"
        ),
        member_path="tables/table-003-region-01.png",
        expected_sha256=(
            "33bc0c8f6926c012500d9102ec7f8fbfcff8f25837ba8dc9ac8453a53e1c147f"
        ),
        expected_bytes=24_285,
        audit_profile="manual_table_text_and_structure",
    ),
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def digest(content: bytes) -> str:
    return SHA256Fingerprinter.fingerprint(content=content)


def identity(namespace: str, value: object) -> str:
    return f"{namespace}:sha256:{digest(canonical(value))}"


def exact(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RuntimeError(f"missing or unsafe file: {path}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(f"missing or unsafe file: {path}")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError(f"file is not private: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read()
        if len(content) != metadata.st_size:
            raise RuntimeError(f"file changed while reading: {path}")
        return content
    finally:
        os.close(descriptor)


def identified(path: Path, key: str, namespace: str) -> dict[str, object]:
    value = json.loads(exact(path))
    if type(value) is not dict:
        raise RuntimeError(f"JSON object required: {path}")
    body = dict(value)
    observed = body.pop(key, None)
    if observed != identity(namespace, body):
        raise RuntimeError(f"identity differs: {path}")
    return value


def private_directory(path: Path) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError(f"unsafe output directory: {path}")
    else:
        path.mkdir(parents=True, mode=0o700)
    os.chmod(path, 0o700)


def create_once(path: Path, content: bytes) -> str:
    if path.exists():
        if exact(path) != content:
            raise RuntimeError(f"create-once artifact differs: {path}")
        return "unchanged"
    private_directory(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return "created"


def relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise RuntimeError(f"unsafe evidence path: {value}")
    return path


def png_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 24 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("evidence is not a PNG")
    if content[12:16] != b"IHDR":
        raise RuntimeError("evidence PNG has no initial IHDR")
    width = int.from_bytes(content[16:20], "big")
    height = int.from_bytes(content[20:24], "big")
    if width <= 0 or height <= 0 or width > 16_384 or height > 16_384:
        raise RuntimeError("evidence PNG dimensions are invalid")
    return width, height


def processor_identity() -> dict[str, object]:
    configuration = OllamaMultimodalConfiguration(
        endpoint=OLLAMA_ENDPOINT,
        model_name=OLLAMA_MODEL,
        expected_model_digest=OLLAMA_DIGEST,
        expected_ollama_version=OLLAMA_VERSION,
        options=OllamaRequestOptions(
            temperature=0.0,
            seed=0,
            context_tokens=8192,
            output_tokens=2048,
            keep_alive="0",
        ),
        limits=OllamaMultimodalLimits(max_selections=1),
        connect_timeout_seconds=5.0,
        read_timeout_seconds=300.0,
    )
    return CanonicalJsonSerializer.project_object(
        OllamaMultimodalRegionProcessor(configuration=configuration).identity()
    )


def replicated_invocations(
    samples: list[dict[str, object]],
    processor: dict[str, object],
) -> list[dict[str, object]]:
    invocations: list[dict[str, object]] = []
    for sample in samples:
        for replicate_ordinal in range(1, REPLICATES_PER_SAMPLE + 1):
            body = {
                "sample_id": sample["sample_id"],
                "sample_key": sample["sample_key"],
                "replicate_ordinal": replicate_ordinal,
                "processor_identity": processor,
                "cache_policy": (
                    "independent_invocation_no_cross_replicate_reuse"
                ),
                "result_path": (
                    f"results/{sample['sample_key']}"
                    f"-replicate-{replicate_ordinal:02d}.json"
                ),
                "execution_status": "not_requested",
            }
            invocations.append(
                {
                    **body,
                    "invocation_id": identity(
                        "reference-ollama-multimodal-replicated-canary-invocation",
                        body,
                    ),
                }
            )
    return invocations


def plan() -> dict[str, object]:
    os.umask(0o077)
    private_directory(OUTPUT)
    processor = processor_identity()
    samples: list[dict[str, object]] = []
    evidence_statuses: dict[str, str] = {}
    verified_sources: set[str] = set()
    for specification in SAMPLES:
        if specification.source_sha256 not in verified_sources:
            source = exact(
                REFERENCES / specification.source_sha256 / "document.pdf"
            )
            if digest(source) != specification.source_sha256:
                raise RuntimeError(
                    f"{specification.sample_key}: source bytes differ"
                )
            verified_sources.add(specification.source_sha256)
        chunk_root = (
            PREPARATION
            / "books"
            / specification.book
            / "chunks"
            / f"chunk-{specification.chunk_number:03d}"
        )
        quality = identified(
            chunk_root / "quality-inventory.json",
            "quality_inventory_id",
            "reference-multimodal-quality-inventory",
        )
        inventory = identified(
            chunk_root / "inventory.json",
            "inventory_id",
            "reference-multimodal-chunk-inventory",
        )
        quality_key = (
            "figures" if specification.evidence_class == "figure" else "tables"
        )
        candidates = quality.get(quality_key)
        members = inventory.get("members")
        if type(candidates) is not list or any(
            type(value) is not dict for value in candidates
        ):
            raise RuntimeError(
                f"{specification.sample_key}: candidates invalid"
            )
        if type(members) is not list or any(
            type(value) is not dict for value in members
        ):
            raise RuntimeError(f"{specification.sample_key}: members invalid")
        matches = [
            value
            for value in candidates
            if value.get("candidate_id") == specification.candidate_id
        ]
        member_matches = [
            value
            for value in members
            if value.get("candidate_id") == specification.candidate_id
            and value.get("path") == specification.member_path
        ]
        if len(matches) != 1 or len(member_matches) != 1:
            raise RuntimeError(
                f"{specification.sample_key}: evidence binding is not unique"
            )
        candidate = matches[0]
        member = member_matches[0]
        if (
            quality.get("book") != specification.book
            or inventory.get("book") != specification.book
            or member.get("sha256") != specification.expected_sha256
            or member.get("bytes") != specification.expected_bytes
            or candidate.get("rendered_members") != [specification.member_path]
        ):
            raise RuntimeError(
                f"{specification.sample_key}: retained evidence differs"
            )
        evidence_path = chunk_root.joinpath(
            *relative_path(specification.member_path).parts
        )
        evidence = exact(evidence_path)
        if (
            len(evidence) != specification.expected_bytes
            or digest(evidence) != specification.expected_sha256
        ):
            raise RuntimeError(
                f"{specification.sample_key}: evidence bytes differ"
            )
        width, height = png_dimensions(evidence)
        retained_path = OUTPUT / "evidence" / f"{specification.sample_key}.png"
        evidence_statuses[specification.sample_key] = create_once(
            retained_path, evidence
        )
        sample_body = {
            "sample_key": specification.sample_key,
            "evidence_class": specification.evidence_class,
            "book": specification.book,
            "source_sha256": specification.source_sha256,
            "chunk_number": specification.chunk_number,
            "candidate_id": specification.candidate_id,
            "page_index": member["page_index"],
            "source_spans": candidate["source_spans"],
            "quality_inventory_id": quality["quality_inventory_id"],
            "inventory_id": inventory["inventory_id"],
            "preparation_member_path": (
                f"books/{specification.book}/chunks/"
                f"chunk-{specification.chunk_number:03d}/"
                f"{specification.member_path}"
            ),
            "retained_evidence_path": (
                f"evidence/{specification.sample_key}.png"
            ),
            "evidence_sha256": specification.expected_sha256,
            "evidence_bytes": specification.expected_bytes,
            "width_pixels": width,
            "height_pixels": height,
            "audit_profile": specification.audit_profile,
            "expected_visible_labels": list(
                specification.expected_visible_labels
            ),
        }
        samples.append(
            {
                **sample_body,
                "sample_id": identity(
                    "reference-ollama-multimodal-replicated-canary-sample",
                    sample_body,
                ),
            }
        )

    invocations = replicated_invocations(samples, processor)
    body = {
        "contract_version": "1.0",
        "authorization": "plan_only_no_model_execution",
        "model_determinism": "nondeterministic",
        "purpose": "observe_variability_and_bounded_content_class_quality",
        "processor_identity": processor,
        "sample_count": len(samples),
        "replicates_per_sample": REPLICATES_PER_SAMPLE,
        "planned_invocation_count": len(invocations),
        "samples": samples,
        "invocations": invocations,
        "comparison_policy": {
            "within_sample": [
                "proposal_text_sha256",
                "proposal_text_utf8_bytes",
                "warnings",
                "missing_visible_content",
                "invented_content",
            ],
            "no_determinism_claim": True,
            "identical_outputs_do_not_establish_determinism": True,
            "different_outputs_are_retained_without_reconciliation": True,
        },
        "output_policy": {
            "automated": True,
            "review_status": "unreviewed",
            "accepted": False,
            "chunk_text_eligible": False,
            "publication_eligible": False,
        },
        "model_execution_performed": False,
    }
    artifact = {
        **body,
        "plan_id": identity(
            "reference-ollama-multimodal-replicated-canary-plan", body
        ),
    }
    content = (
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()
    status = create_once(OUTPUT / "plan.json", content)
    return {
        "plan_id": artifact["plan_id"],
        "plan_sha256": digest(content),
        "plan_bytes": len(content),
        "plan_status": status,
        "sample_count": len(samples),
        "planned_invocation_count": len(invocations),
        "evidence_statuses": dict(sorted(evidence_statuses.items())),
        "model_determinism": "nondeterministic",
        "model_execution_performed": False,
        "execution_authorized": False,
    }


def main() -> None:
    print(json.dumps(plan(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
