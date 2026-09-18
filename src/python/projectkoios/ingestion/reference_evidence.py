from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from projectkoios.ingestion.identity import canonical_json, stable_id
from projectkoios.ingestion.models import (
    CONTRACT_VERSION,
    ExtractionResult,
    IngestionStatus,
)
from projectkoios.ingestion.provenance import (
    DERIVATION_AUDIT_CONTRACT_VERSION,
    DerivationAuditReport,
    DerivationAuditStatus,
)
from projectkoios.ingestion.serialization import (
    contract_dict,
    serialize_contract,
)
from projectkoios.ingestion.transcript_projection import (
    CLEAN_TRANSCRIPT_CONTRACT_VERSION,
    CleanTranscriptArtifact,
    CleanTranscriptStatus,
)

REFERENCE_EVIDENCE_CONTRACT_ID = "projectkoios.ingestion.reference-evidence"
REFERENCE_EVIDENCE_CONTRACT_VERSION = "0.1.0"
REFERENCE_EVIDENCE_SCHEMA_VERSION = 1
REFERENCE_EVIDENCE_GENERATOR_NAME = "projectkoios-ingestion-reference-evidence"
REFERENCE_EVIDENCE_GENERATOR_VERSION = "1"
REFERENCE_EVIDENCE_MEDIA_TYPE = (
    "application/vnd.projectkoios.ingestion.reference-evidence+json"
)
REFERENCE_EVIDENCE_MAX_BYTES = 262_144
REFERENCE_EVIDENCE_MAX_LINEAGE_IDS = 4_096
REFERENCE_EVIDENCE_MAX_LAYOUT_IDS = 512
REFERENCE_EVIDENCE_MAX_LAYER_COUNTS = 32
REFERENCE_EVIDENCE_MAX_LIMITATIONS = 32
REFERENCE_EVIDENCE_TRANSCRIPT_GENERATION = 1
_MAX_BOUND_ARTIFACT_BYTES = 128_000_000
_MAX_JSON_DEPTH = 64
_MAX_STRING_CHARACTERS = 4_096
_SHA256_LENGTH = 64
_EXTRACTION_MEDIA_TYPE = (
    "application/vnd.projectkoios.ingestion.extraction+json"
)
_CLEAN_TRANSCRIPT_MEDIA_TYPE = (
    "application/vnd.projectkoios.ingestion.clean-transcript+json"
)
_DERIVATION_AUDIT_MEDIA_TYPE = (
    "application/vnd.projectkoios.ingestion.derivation-audit+json"
)
_REQUIRED_LIMITATIONS = (
    "automated_unreviewed",
    "not_extraction_accuracy_verification",
    "not_human_proofread",
    "not_independent_revalidation",
    "not_producer_authentication",
    "not_publication_suitable",
    "not_scientifically_validated",
    "not_semantically_corrected",
)


class ReferenceEvidenceError(ValueError):
    """Base error for the bounded reference-evidence projection."""


class ReferenceEvidenceLimitError(ReferenceEvidenceError):
    """Raised before reference-evidence processing exceeds a hard bound."""


class ReferenceEvidenceParseError(ReferenceEvidenceError):
    """Raised when external reference-evidence bytes are not canonical."""


class ReferenceEvidenceVerificationError(ReferenceEvidenceError):
    """Raised when evidence is unusable or does not match expected bytes."""


class ReferenceEvidenceContractStatus(StrEnum):
    PROPOSED = "proposed"


class ReferenceEvidenceCompleteness(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNSUPPORTED = "unsupported"


class ReferenceEvidenceAuditScope(StrEnum):
    RECORDED_PRODUCER_DERIVATION_AUDIT = "recorded_producer_derivation_audit"


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > _MAX_STRING_CHARACTERS:
        raise ReferenceEvidenceLimitError(f"{name} exceeds the string limit")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error
    return value


def _require_nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _require_sha256(value: object, name: str) -> str:
    digest = _require_text(value, name)
    if len(digest) != _SHA256_LENGTH or digest != digest.lower():
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    try:
        int(digest, 16)
    except ValueError as error:
        raise ValueError(
            f"{name} must be a lowercase SHA-256 digest"
        ) from error
    return digest


def _require_tuple(value: object, name: str, maximum: int) -> tuple[Any, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    if len(value) > maximum:
        raise ReferenceEvidenceLimitError(f"{name} exceeds the item limit")
    return value


@dataclass(frozen=True)
class ReferenceEvidenceArtifact:
    media_type: str
    sha256: str
    byte_length: int

    @classmethod
    def from_bytes(
        cls, content: bytes, *, media_type: str
    ) -> ReferenceEvidenceArtifact:
        if not isinstance(content, bytes):
            raise TypeError("artifact content must be bytes")
        if len(content) > _MAX_BOUND_ARTIFACT_BYTES:
            raise ReferenceEvidenceLimitError(
                "bound artifact exceeds size limit"
            )
        return cls(
            media_type=media_type,
            sha256=hashlib.sha256(content).hexdigest(),
            byte_length=len(content),
        )

    def __post_init__(self) -> None:
        _require_text(self.media_type, "artifact media_type")
        _require_sha256(self.sha256, "artifact sha256")
        _require_nonnegative_int(self.byte_length, "artifact byte_length")
        if self.byte_length > _MAX_BOUND_ARTIFACT_BYTES:
            raise ReferenceEvidenceLimitError(
                "bound artifact exceeds size limit"
            )

    def verify(self, content: bytes, *, name: str) -> None:
        if not isinstance(content, bytes):
            raise TypeError(f"{name} must be bytes")
        if len(content) > _MAX_BOUND_ARTIFACT_BYTES:
            raise ReferenceEvidenceLimitError(f"{name} exceeds size limit")
        actual = hashlib.sha256(content).hexdigest()
        if len(content) != self.byte_length or actual != self.sha256:
            raise ReferenceEvidenceVerificationError(
                f"{name} does not match its recorded content identity"
            )


@dataclass(frozen=True)
class ReferenceEvidenceSource:
    blob_id: str
    hash_algorithm: str
    content_sha256: str
    byte_length: int
    media_type: str

    def __post_init__(self) -> None:
        _require_text(self.blob_id, "source blob_id")
        if self.hash_algorithm != "sha256":
            raise ValueError("only sha256 source identity is supported")
        _require_sha256(self.content_sha256, "source content_sha256")
        if self.blob_id != f"blob:sha256:{self.content_sha256}":
            raise ValueError("source blob_id does not match content_sha256")
        _require_nonnegative_int(self.byte_length, "source byte_length")
        _require_text(self.media_type, "source media_type")


@dataclass(frozen=True)
class ReferenceEvidenceExtraction:
    artifact: ReferenceEvidenceArtifact
    contract_version: str
    manifest_id: str
    document_id: str
    status: IngestionStatus
    extractor_name: str
    extractor_version: str
    configuration_digest: str
    warning_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, ReferenceEvidenceArtifact):
            raise TypeError("extraction artifact identity is required")
        if self.artifact.media_type != _EXTRACTION_MEDIA_TYPE:
            raise ValueError("unsupported extraction artifact media type")
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("unsupported extraction contract version")
        _require_text(self.manifest_id, "extraction manifest_id")
        _require_text(self.document_id, "extraction document_id")
        if not isinstance(self.status, IngestionStatus):
            raise TypeError("extraction status is unsupported")
        _require_text(self.extractor_name, "extractor name")
        _require_text(self.extractor_version, "extractor version")
        _require_text(self.configuration_digest, "extraction configuration")
        _require_nonnegative_int(self.warning_count, "extraction warning_count")


@dataclass(frozen=True)
class ReferenceEvidenceTranscript:
    artifact: ReferenceEvidenceArtifact
    artifact_generation: int
    contract_version: str
    artifact_id: str
    status: CleanTranscriptStatus
    structured_transcription_result_id: str
    layout_result_ids: tuple[str, ...]
    text_sha256: str
    text_utf8_byte_length: int
    processor_name: str
    processor_version: str
    configuration_digest: str
    warning_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, ReferenceEvidenceArtifact):
            raise TypeError("transcript artifact identity is required")
        if self.artifact.media_type != _CLEAN_TRANSCRIPT_MEDIA_TYPE:
            raise ValueError("unsupported transcript artifact media type")
        if (
            isinstance(self.artifact_generation, bool)
            or self.artifact_generation
            != REFERENCE_EVIDENCE_TRANSCRIPT_GENERATION
        ):
            raise ValueError("unsupported transcript artifact generation")
        if self.contract_version != CLEAN_TRANSCRIPT_CONTRACT_VERSION:
            raise ValueError("unsupported clean-transcript contract version")
        _require_text(self.artifact_id, "transcript artifact_id")
        if not isinstance(self.status, CleanTranscriptStatus):
            raise TypeError("transcript status is unsupported")
        _require_text(
            self.structured_transcription_result_id,
            "structured transcription result_id",
        )
        _require_tuple(
            self.layout_result_ids,
            "transcript layout_result_ids",
            REFERENCE_EVIDENCE_MAX_LAYOUT_IDS,
        )
        if not self.layout_result_ids:
            raise ValueError("transcript layout_result_ids must be non-empty")
        if len(set(self.layout_result_ids)) != len(self.layout_result_ids):
            raise ValueError("transcript layout_result_ids must be unique")
        for index, identity in enumerate(self.layout_result_ids):
            _require_text(identity, f"transcript layout_result_ids[{index}]")
        _require_sha256(self.text_sha256, "transcript text_sha256")
        _require_nonnegative_int(
            self.text_utf8_byte_length, "transcript text_utf8_byte_length"
        )
        _require_text(self.processor_name, "transcript processor_name")
        _require_text(self.processor_version, "transcript processor_version")
        _require_text(
            self.configuration_digest, "transcript configuration_digest"
        )
        _require_nonnegative_int(self.warning_count, "transcript warning_count")


@dataclass(frozen=True)
class ReferenceEvidenceLayerCount:
    layer: str
    count: int

    def __post_init__(self) -> None:
        _require_text(self.layer, "audit layer")
        _require_nonnegative_int(self.count, "audit layer count")


@dataclass(frozen=True)
class ReferenceEvidenceAudit:
    artifact: ReferenceEvidenceArtifact
    contract_version: str
    report_id: str
    status: DerivationAuditStatus
    scope: ReferenceEvidenceAuditScope
    independently_revalidated: bool
    processor_name: str
    processor_version: str
    audited_artifact_ids: tuple[str, ...]
    audited_layer_counts: tuple[ReferenceEvidenceLayerCount, ...]
    finding_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, ReferenceEvidenceArtifact):
            raise TypeError("audit artifact identity is required")
        if self.artifact.media_type != _DERIVATION_AUDIT_MEDIA_TYPE:
            raise ValueError("unsupported audit artifact media type")
        if self.contract_version != DERIVATION_AUDIT_CONTRACT_VERSION:
            raise ValueError("unsupported derivation-audit contract version")
        _require_text(self.report_id, "audit report_id")
        if not isinstance(self.status, DerivationAuditStatus):
            raise TypeError("audit status is unsupported")
        if not isinstance(self.scope, ReferenceEvidenceAuditScope):
            raise TypeError("audit scope is unsupported")
        if self.independently_revalidated is not False:
            raise ValueError(
                "reference evidence cannot claim independent revalidation"
            )
        _require_text(self.processor_name, "audit processor_name")
        _require_text(self.processor_version, "audit processor_version")
        _require_tuple(
            self.audited_artifact_ids,
            "audit audited_artifact_ids",
            REFERENCE_EVIDENCE_MAX_LINEAGE_IDS,
        )
        if not self.audited_artifact_ids:
            raise ValueError("audit audited_artifact_ids must be non-empty")
        if len(set(self.audited_artifact_ids)) != len(
            self.audited_artifact_ids
        ):
            raise ValueError("audit audited_artifact_ids must be unique")
        for index, identity in enumerate(self.audited_artifact_ids):
            _require_text(identity, f"audit audited_artifact_ids[{index}]")
        _require_tuple(
            self.audited_layer_counts,
            "audit audited_layer_counts",
            REFERENCE_EVIDENCE_MAX_LAYER_COUNTS,
        )
        if any(
            not isinstance(item, ReferenceEvidenceLayerCount)
            for item in self.audited_layer_counts
        ):
            raise TypeError("audit layer counts contain an unsupported value")
        layers = tuple(item.layer for item in self.audited_layer_counts)
        if tuple(sorted(layers)) != layers or len(set(layers)) != len(layers):
            raise ValueError("audit layer counts must be unique and sorted")
        _require_nonnegative_int(self.finding_count, "audit finding_count")


@dataclass(frozen=True)
class ReferenceEvidenceRecord:
    record_id: str
    contract_id: str
    contract_version: str
    contract_status: ReferenceEvidenceContractStatus
    schema_version: int
    media_type: str
    generator_name: str
    generator_version: str
    completeness: ReferenceEvidenceCompleteness
    completeness_reasons: tuple[str, ...]
    source: ReferenceEvidenceSource
    extraction: ReferenceEvidenceExtraction
    transcript: ReferenceEvidenceTranscript
    derivation_audit: ReferenceEvidenceAudit
    limitations: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        source: ReferenceEvidenceSource,
        extraction: ReferenceEvidenceExtraction,
        transcript: ReferenceEvidenceTranscript,
        derivation_audit: ReferenceEvidenceAudit,
        completeness: ReferenceEvidenceCompleteness = (
            ReferenceEvidenceCompleteness.COMPLETE
        ),
        completeness_reasons: tuple[str, ...] = (),
        limitations: tuple[str, ...] = _REQUIRED_LIMITATIONS,
    ) -> ReferenceEvidenceRecord:
        normalized_reasons = tuple(sorted(completeness_reasons))
        normalized_limitations = tuple(sorted(limitations))
        identity = cls._identity(
            contract_id=REFERENCE_EVIDENCE_CONTRACT_ID,
            contract_version=REFERENCE_EVIDENCE_CONTRACT_VERSION,
            contract_status=ReferenceEvidenceContractStatus.PROPOSED,
            schema_version=REFERENCE_EVIDENCE_SCHEMA_VERSION,
            media_type=REFERENCE_EVIDENCE_MEDIA_TYPE,
            generator_name=REFERENCE_EVIDENCE_GENERATOR_NAME,
            generator_version=REFERENCE_EVIDENCE_GENERATOR_VERSION,
            completeness=completeness,
            completeness_reasons=normalized_reasons,
            source=source,
            extraction=extraction,
            transcript=transcript,
            derivation_audit=derivation_audit,
            limitations=normalized_limitations,
        )
        return cls(
            record_id=identity,
            contract_id=REFERENCE_EVIDENCE_CONTRACT_ID,
            contract_version=REFERENCE_EVIDENCE_CONTRACT_VERSION,
            contract_status=ReferenceEvidenceContractStatus.PROPOSED,
            schema_version=REFERENCE_EVIDENCE_SCHEMA_VERSION,
            media_type=REFERENCE_EVIDENCE_MEDIA_TYPE,
            generator_name=REFERENCE_EVIDENCE_GENERATOR_NAME,
            generator_version=REFERENCE_EVIDENCE_GENERATOR_VERSION,
            completeness=completeness,
            completeness_reasons=normalized_reasons,
            source=source,
            extraction=extraction,
            transcript=transcript,
            derivation_audit=derivation_audit,
            limitations=normalized_limitations,
        )

    @staticmethod
    def _identity(**values: object) -> str:
        return stable_id("reference-evidence-record", values)

    def __post_init__(self) -> None:
        _require_text(self.record_id, "reference-evidence record_id")
        if self.contract_id != REFERENCE_EVIDENCE_CONTRACT_ID:
            raise ValueError("unsupported reference-evidence contract ID")
        if self.contract_version != REFERENCE_EVIDENCE_CONTRACT_VERSION:
            raise ValueError("unsupported reference-evidence contract version")
        if self.contract_status is not ReferenceEvidenceContractStatus.PROPOSED:
            raise ValueError("unsupported reference-evidence contract status")
        if (
            isinstance(self.schema_version, bool)
            or self.schema_version != REFERENCE_EVIDENCE_SCHEMA_VERSION
        ):
            raise ValueError("unsupported reference-evidence schema version")
        if self.media_type != REFERENCE_EVIDENCE_MEDIA_TYPE:
            raise ValueError("unsupported reference-evidence media type")
        if self.generator_name != REFERENCE_EVIDENCE_GENERATOR_NAME:
            raise ValueError("unsupported reference-evidence generator")
        if self.generator_version != REFERENCE_EVIDENCE_GENERATOR_VERSION:
            raise ValueError("unsupported reference-evidence generator version")
        if not isinstance(self.completeness, ReferenceEvidenceCompleteness):
            raise TypeError("reference-evidence completeness is unsupported")
        _require_tuple(
            self.completeness_reasons,
            "reference-evidence completeness_reasons",
            REFERENCE_EVIDENCE_MAX_LIMITATIONS,
        )
        if (
            tuple(sorted(self.completeness_reasons))
            != self.completeness_reasons
        ):
            raise ValueError("completeness reasons must be sorted")
        for index, reason in enumerate(self.completeness_reasons):
            _require_text(reason, f"completeness_reasons[{index}]")
        if self.completeness is ReferenceEvidenceCompleteness.COMPLETE:
            if self.completeness_reasons:
                raise ValueError(
                    "complete evidence cannot have failure reasons"
                )
        elif not self.completeness_reasons:
            raise ValueError("non-complete evidence requires explicit reasons")
        if not isinstance(self.source, ReferenceEvidenceSource):
            raise TypeError("reference-evidence source is required")
        if not isinstance(self.extraction, ReferenceEvidenceExtraction):
            raise TypeError("reference-evidence extraction is required")
        if not isinstance(self.transcript, ReferenceEvidenceTranscript):
            raise TypeError("reference-evidence transcript is required")
        if not isinstance(self.derivation_audit, ReferenceEvidenceAudit):
            raise TypeError("reference-evidence derivation audit is required")
        _require_tuple(
            self.limitations,
            "reference-evidence limitations",
            REFERENCE_EVIDENCE_MAX_LIMITATIONS,
        )
        if tuple(sorted(self.limitations)) != self.limitations:
            raise ValueError("reference-evidence limitations must be sorted")
        if not set(_REQUIRED_LIMITATIONS).issubset(self.limitations):
            raise ValueError("reference-evidence limitations are incomplete")
        if self.completeness is ReferenceEvidenceCompleteness.COMPLETE:
            self._validate_complete_lineage()
        expected = self._identity(
            contract_id=self.contract_id,
            contract_version=self.contract_version,
            contract_status=self.contract_status,
            schema_version=self.schema_version,
            media_type=self.media_type,
            generator_name=self.generator_name,
            generator_version=self.generator_version,
            completeness=self.completeness,
            completeness_reasons=self.completeness_reasons,
            source=self.source,
            extraction=self.extraction,
            transcript=self.transcript,
            derivation_audit=self.derivation_audit,
            limitations=self.limitations,
        )
        if self.record_id != expected:
            raise ValueError("reference-evidence record ID is inconsistent")
        if (
            len(serialize_reference_evidence(self))
            > REFERENCE_EVIDENCE_MAX_BYTES
        ):
            raise ReferenceEvidenceLimitError(
                "reference-evidence serialization exceeds size limit"
            )

    def _validate_complete_lineage(self) -> None:
        if self.extraction.status is not IngestionStatus.COMPLETED:
            raise ValueError("complete evidence requires completed extraction")
        if (
            self.transcript.status
            is not CleanTranscriptStatus.AUTOMATED_UNREVIEWED
        ):
            raise ValueError(
                "complete evidence requires automated-unreviewed "
                "transcript status"
            )
        audit = self.derivation_audit
        if audit.status is not DerivationAuditStatus.PASSED:
            raise ValueError(
                "complete evidence requires a recorded passing audit"
            )
        if audit.finding_count != 0:
            raise ValueError("passing derivation audit cannot contain findings")
        required_ids = {
            self.extraction.manifest_id,
            self.extraction.document_id,
            self.transcript.structured_transcription_result_id,
            self.transcript.artifact_id,
            *self.transcript.layout_result_ids,
        }
        if not required_ids.issubset(audit.audited_artifact_ids):
            raise ValueError(
                "derivation audit does not cover complete "
                "extraction/transcript lineage"
            )
        counts = {item.layer: item.count for item in audit.audited_layer_counts}
        required_counts = {
            "extraction_result": 1,
            "transcription_results": 1,
            "clean_transcript_artifacts": 1,
        }
        if any(
            counts.get(name) != value for name, value in required_counts.items()
        ):
            raise ValueError("derivation audit layer coverage is incomplete")
        if counts.get("layout_results") != len(
            self.transcript.layout_result_ids
        ):
            raise ValueError("derivation audit layout coverage is incomplete")

    def require_reusable(self) -> None:
        if self.completeness is not ReferenceEvidenceCompleteness.COMPLETE:
            reasons = ", ".join(self.completeness_reasons)
            raise ReferenceEvidenceVerificationError(
                f"reference evidence is {self.completeness.value}: {reasons}"
            )
        self._validate_complete_lineage()


def _canonical_artifact_bytes(value: object) -> bytes:
    return (serialize_contract(value) + "\n").encode("utf-8")


def _parse_json_bytes(content: bytes, *, name: str, maximum: int) -> object:
    if not isinstance(content, bytes):
        raise TypeError(f"{name} must be bytes")
    if len(content) > maximum:
        raise ReferenceEvidenceLimitError(f"{name} exceeds size limit")
    try:
        text = content.decode("utf-8", errors="strict")
        _require_bounded_json_nesting(text)
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as error:
        raise ReferenceEvidenceParseError(
            f"{name} is malformed JSON: {error}"
        ) from error


def _verify_extraction_artifact(
    content: bytes, extraction_result: ExtractionResult
) -> None:
    value = _parse_json_bytes(
        content,
        name="extraction artifact",
        maximum=_MAX_BOUND_ARTIFACT_BYTES,
    )
    if not isinstance(value, dict):
        raise ReferenceEvidenceVerificationError(
            "extraction artifact root must be an object"
        )
    try:
        if (canonical_json(value) + "\n").encode("utf-8") != content:
            raise ReferenceEvidenceVerificationError(
                "extraction artifact serialization is noncanonical"
            )
    except (UnicodeEncodeError, ValueError, RecursionError) as error:
        raise ReferenceEvidenceVerificationError(
            "extraction artifact cannot be canonicalized"
        ) from error
    expected = contract_dict(extraction_result)
    if set(value) != set(expected):
        raise ReferenceEvidenceVerificationError(
            "extraction artifact fields do not match ExtractionResult"
        )
    if (
        value.get("document") != expected["document"]
        or value.get("warnings") != expected["warnings"]
    ):
        raise ReferenceEvidenceVerificationError(
            "extraction artifact content does not match ExtractionResult"
        )
    actual_manifest = value.get("manifest")
    expected_manifest = expected["manifest"]
    if not isinstance(actual_manifest, dict) or not isinstance(
        expected_manifest, dict
    ):
        raise ReferenceEvidenceVerificationError(
            "extraction artifact manifest is malformed"
        )
    if set(actual_manifest) != set(expected_manifest):
        raise ReferenceEvidenceVerificationError(
            "extraction artifact manifest fields are unsupported"
        )
    for key, expected_value in expected_manifest.items():
        if key in {"started_at", "completed_at"}:
            actual_value = actual_manifest.get(key)
            if actual_value is not None and not isinstance(actual_value, str):
                raise ReferenceEvidenceVerificationError(
                    "extraction artifact timestamps are malformed"
                )
            continue
        if actual_manifest.get(key) != expected_value:
            raise ReferenceEvidenceVerificationError(
                "extraction artifact manifest contradicts ExtractionResult"
            )


def build_reference_evidence(
    *,
    extraction_result: ExtractionResult,
    extraction_artifact: bytes,
    clean_transcript: CleanTranscriptArtifact,
    clean_transcript_artifact: bytes,
    derivation_audit: DerivationAuditReport,
    derivation_audit_artifact: bytes,
) -> ReferenceEvidenceRecord:
    """Build one complete projection from exact, already-produced artifacts.

    The derivation-audit status is recorded producer evidence. This function
    verifies lineage and artifact bytes but does not independently re-run the
    derivation audit or assess extraction accuracy.
    """

    if not isinstance(extraction_result, ExtractionResult):
        raise TypeError("extraction_result must be ExtractionResult")
    if not isinstance(clean_transcript, CleanTranscriptArtifact):
        raise TypeError("clean_transcript must be CleanTranscriptArtifact")
    if not isinstance(derivation_audit, DerivationAuditReport):
        raise TypeError("derivation_audit must be DerivationAuditReport")
    _verify_extraction_artifact(extraction_artifact, extraction_result)
    if clean_transcript_artifact != _canonical_artifact_bytes(clean_transcript):
        raise ReferenceEvidenceVerificationError(
            "clean-transcript artifact does not match its immutable contract"
        )
    if derivation_audit_artifact != _canonical_artifact_bytes(derivation_audit):
        raise ReferenceEvidenceVerificationError(
            "derivation-audit artifact does not match its immutable contract"
        )

    document = extraction_result.document
    source = document.source
    manifest = extraction_result.manifest
    if manifest.status is not IngestionStatus.COMPLETED:
        raise ReferenceEvidenceVerificationError(
            "incomplete extraction cannot produce complete reference evidence"
        )
    if (
        clean_transcript.status
        is not CleanTranscriptStatus.AUTOMATED_UNREVIEWED
    ):
        raise ReferenceEvidenceVerificationError(
            "unsupported clean-transcript status"
        )
    if (
        clean_transcript.document_id != document.document_id
        or clean_transcript.source_id != source.source_id
        or clean_transcript.source_blob_id != source.blob_id
        or clean_transcript.source_content_hash != source.content_hash
    ):
        raise ReferenceEvidenceVerificationError(
            "clean transcript does not match extraction source bytes"
        )
    if (
        derivation_audit.source_id != source.source_id
        or derivation_audit.source_blob_id != source.blob_id
        or derivation_audit.source_content_hash != source.content_hash
        or derivation_audit.document_id != document.document_id
    ):
        raise ReferenceEvidenceVerificationError(
            "derivation audit does not match extraction source bytes"
        )
    if derivation_audit.status is not DerivationAuditStatus.PASSED:
        raise ReferenceEvidenceVerificationError(
            "failed derivation audit cannot produce complete reference evidence"
        )
    if derivation_audit.findings:
        raise ReferenceEvidenceVerificationError(
            "passing derivation audit contains contradictory findings"
        )

    try:
        layer_counts = tuple(
            ReferenceEvidenceLayerCount(layer=name, count=int(count))
            for name, count in derivation_audit.audited_layer_counts
        )
    except (TypeError, ValueError) as error:
        raise ReferenceEvidenceVerificationError(
            "derivation audit layer counts are malformed"
        ) from error

    return ReferenceEvidenceRecord.create(
        source=ReferenceEvidenceSource(
            blob_id=source.blob_id,
            hash_algorithm=source.hash_algorithm,
            content_sha256=source.content_hash,
            byte_length=source.byte_length,
            media_type=source.media_type,
        ),
        extraction=ReferenceEvidenceExtraction(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                extraction_artifact, media_type=_EXTRACTION_MEDIA_TYPE
            ),
            contract_version=document.contract_version,
            manifest_id=manifest.manifest_id,
            document_id=document.document_id,
            status=manifest.status,
            extractor_name=manifest.extractor_name,
            extractor_version=manifest.extractor_version,
            configuration_digest=manifest.configuration_digest,
            warning_count=len(extraction_result.warnings),
        ),
        transcript=ReferenceEvidenceTranscript(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                clean_transcript_artifact,
                media_type=_CLEAN_TRANSCRIPT_MEDIA_TYPE,
            ),
            artifact_generation=REFERENCE_EVIDENCE_TRANSCRIPT_GENERATION,
            contract_version=clean_transcript.contract_version,
            artifact_id=clean_transcript.artifact_id,
            status=clean_transcript.status,
            structured_transcription_result_id=(
                clean_transcript.transcription_result_id
            ),
            layout_result_ids=clean_transcript.layout_result_ids,
            text_sha256=clean_transcript.text_sha256,
            text_utf8_byte_length=clean_transcript.utf8_byte_length,
            processor_name=clean_transcript.processor_name,
            processor_version=clean_transcript.processor_version,
            configuration_digest=clean_transcript.configuration_digest,
            warning_count=len(clean_transcript.warnings),
        ),
        derivation_audit=ReferenceEvidenceAudit(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                derivation_audit_artifact,
                media_type=_DERIVATION_AUDIT_MEDIA_TYPE,
            ),
            contract_version=derivation_audit.contract_version,
            report_id=derivation_audit.report_id,
            status=derivation_audit.status,
            scope=(
                ReferenceEvidenceAuditScope.RECORDED_PRODUCER_DERIVATION_AUDIT
            ),
            independently_revalidated=False,
            processor_name=derivation_audit.processor_name,
            processor_version=derivation_audit.processor_version,
            audited_artifact_ids=derivation_audit.audited_artifact_ids,
            audited_layer_counts=layer_counts,
            finding_count=len(derivation_audit.findings),
        ),
    )


def serialize_reference_evidence(record: ReferenceEvidenceRecord) -> bytes:
    if not isinstance(record, ReferenceEvidenceRecord):
        raise TypeError("record must be ReferenceEvidenceRecord")
    try:
        payload = canonical_json(record).encode("utf-8", errors="strict")
    except (UnicodeEncodeError, ValueError, RecursionError) as error:
        raise ReferenceEvidenceError(
            "reference evidence cannot be canonically serialized"
        ) from error
    if len(payload) > REFERENCE_EVIDENCE_MAX_BYTES:
        raise ReferenceEvidenceLimitError(
            "reference-evidence serialization exceeds size limit"
        )
    return payload


def parse_reference_evidence(content: bytes) -> ReferenceEvidenceRecord:
    """Strictly parse canonical external bytes and require reusable evidence."""

    value = _parse_json_bytes(
        content,
        name="reference evidence",
        maximum=REFERENCE_EVIDENCE_MAX_BYTES,
    )
    try:
        record = _decode_record(value)
        if serialize_reference_evidence(record) != content:
            raise ReferenceEvidenceParseError(
                "reference evidence is not canonical serialization"
            )
        record.require_reusable()
        return record
    except ReferenceEvidenceError:
        raise
    except (KeyError, TypeError, ValueError, RecursionError) as error:
        raise ReferenceEvidenceParseError(
            f"reference evidence is invalid: {error}"
        ) from error


def verify_reference_evidence(
    record: ReferenceEvidenceRecord,
    *,
    source_sha256: str,
    source_byte_length: int,
    source_media_type: str,
    extraction_artifact: bytes | None = None,
    clean_transcript_artifact: bytes | None = None,
    derivation_audit_artifact: bytes | None = None,
) -> None:
    """Verify consumer-known source identity and optional exact artifacts.

    This verifies hashes and the record's producer-reported lineage. It does not
    independently re-run extraction or the derivation audit.
    """

    if not isinstance(record, ReferenceEvidenceRecord):
        raise TypeError("record must be ReferenceEvidenceRecord")
    record.require_reusable()
    expected_sha256 = _require_sha256(source_sha256, "expected source_sha256")
    expected_size = _require_nonnegative_int(
        source_byte_length, "expected source_byte_length"
    )
    expected_media_type = _require_text(
        source_media_type, "expected source_media_type"
    )
    source = record.source
    if (
        source.content_sha256 != expected_sha256
        or source.byte_length != expected_size
        or source.media_type != expected_media_type
        or source.blob_id != f"blob:sha256:{expected_sha256}"
    ):
        raise ReferenceEvidenceVerificationError(
            "reference evidence does not match the expected source bytes"
        )
    optional_artifacts = (
        (
            "extraction artifact",
            record.extraction.artifact,
            extraction_artifact,
        ),
        (
            "clean-transcript artifact",
            record.transcript.artifact,
            clean_transcript_artifact,
        ),
        (
            "derivation-audit artifact",
            record.derivation_audit.artifact,
            derivation_audit_artifact,
        ),
    )
    for name, identity, content in optional_artifacts:
        if content is not None:
            identity.verify(content, name=name)


def _decode_record(value: object) -> ReferenceEvidenceRecord:
    root = _mapping(
        value,
        "reference evidence",
        {
            "record_id",
            "contract_id",
            "contract_version",
            "contract_status",
            "schema_version",
            "media_type",
            "generator_name",
            "generator_version",
            "completeness",
            "completeness_reasons",
            "source",
            "extraction",
            "transcript",
            "derivation_audit",
            "limitations",
        },
    )
    source_value = _mapping(
        root["source"],
        "source",
        {
            "blob_id",
            "hash_algorithm",
            "content_sha256",
            "byte_length",
            "media_type",
        },
    )
    extraction_value = _mapping(
        root["extraction"],
        "extraction",
        {
            "artifact",
            "contract_version",
            "manifest_id",
            "document_id",
            "status",
            "extractor_name",
            "extractor_version",
            "configuration_digest",
            "warning_count",
        },
    )
    transcript_value = _mapping(
        root["transcript"],
        "transcript",
        {
            "artifact",
            "artifact_generation",
            "contract_version",
            "artifact_id",
            "status",
            "structured_transcription_result_id",
            "layout_result_ids",
            "text_sha256",
            "text_utf8_byte_length",
            "processor_name",
            "processor_version",
            "configuration_digest",
            "warning_count",
        },
    )
    audit_value = _mapping(
        root["derivation_audit"],
        "derivation_audit",
        {
            "artifact",
            "contract_version",
            "report_id",
            "status",
            "scope",
            "independently_revalidated",
            "processor_name",
            "processor_version",
            "audited_artifact_ids",
            "audited_layer_counts",
            "finding_count",
        },
    )
    return ReferenceEvidenceRecord(
        record_id=_string(root["record_id"], "record_id"),
        contract_id=_string(root["contract_id"], "contract_id"),
        contract_version=_string(root["contract_version"], "contract_version"),
        contract_status=_enum(
            ReferenceEvidenceContractStatus,
            root["contract_status"],
            "contract_status",
        ),
        schema_version=_integer(root["schema_version"], "schema_version"),
        media_type=_string(root["media_type"], "media_type"),
        generator_name=_string(root["generator_name"], "generator_name"),
        generator_version=_string(
            root["generator_version"], "generator_version"
        ),
        completeness=_enum(
            ReferenceEvidenceCompleteness,
            root["completeness"],
            "completeness",
        ),
        completeness_reasons=_string_tuple(
            root["completeness_reasons"],
            "completeness_reasons",
            REFERENCE_EVIDENCE_MAX_LIMITATIONS,
        ),
        source=ReferenceEvidenceSource(
            blob_id=_string(source_value["blob_id"], "source.blob_id"),
            hash_algorithm=_string(
                source_value["hash_algorithm"], "source.hash_algorithm"
            ),
            content_sha256=_string(
                source_value["content_sha256"], "source.content_sha256"
            ),
            byte_length=_integer(
                source_value["byte_length"], "source.byte_length"
            ),
            media_type=_string(source_value["media_type"], "source.media_type"),
        ),
        extraction=ReferenceEvidenceExtraction(
            artifact=_decode_artifact(
                extraction_value["artifact"], "extraction.artifact"
            ),
            contract_version=_string(
                extraction_value["contract_version"],
                "extraction.contract_version",
            ),
            manifest_id=_string(
                extraction_value["manifest_id"], "extraction.manifest_id"
            ),
            document_id=_string(
                extraction_value["document_id"], "extraction.document_id"
            ),
            status=_enum(
                IngestionStatus, extraction_value["status"], "extraction.status"
            ),
            extractor_name=_string(
                extraction_value["extractor_name"], "extraction.extractor_name"
            ),
            extractor_version=_string(
                extraction_value["extractor_version"],
                "extraction.extractor_version",
            ),
            configuration_digest=_string(
                extraction_value["configuration_digest"],
                "extraction.configuration_digest",
            ),
            warning_count=_integer(
                extraction_value["warning_count"], "extraction.warning_count"
            ),
        ),
        transcript=ReferenceEvidenceTranscript(
            artifact=_decode_artifact(
                transcript_value["artifact"], "transcript.artifact"
            ),
            artifact_generation=_integer(
                transcript_value["artifact_generation"],
                "transcript.artifact_generation",
            ),
            contract_version=_string(
                transcript_value["contract_version"],
                "transcript.contract_version",
            ),
            artifact_id=_string(
                transcript_value["artifact_id"], "transcript.artifact_id"
            ),
            status=_enum(
                CleanTranscriptStatus,
                transcript_value["status"],
                "transcript.status",
            ),
            structured_transcription_result_id=_string(
                transcript_value["structured_transcription_result_id"],
                "transcript.structured_transcription_result_id",
            ),
            layout_result_ids=_string_tuple(
                transcript_value["layout_result_ids"],
                "transcript.layout_result_ids",
                REFERENCE_EVIDENCE_MAX_LAYOUT_IDS,
            ),
            text_sha256=_string(
                transcript_value["text_sha256"], "transcript.text_sha256"
            ),
            text_utf8_byte_length=_integer(
                transcript_value["text_utf8_byte_length"],
                "transcript.text_utf8_byte_length",
            ),
            processor_name=_string(
                transcript_value["processor_name"],
                "transcript.processor_name",
            ),
            processor_version=_string(
                transcript_value["processor_version"],
                "transcript.processor_version",
            ),
            configuration_digest=_string(
                transcript_value["configuration_digest"],
                "transcript.configuration_digest",
            ),
            warning_count=_integer(
                transcript_value["warning_count"], "transcript.warning_count"
            ),
        ),
        derivation_audit=ReferenceEvidenceAudit(
            artifact=_decode_artifact(
                audit_value["artifact"], "derivation_audit.artifact"
            ),
            contract_version=_string(
                audit_value["contract_version"],
                "derivation_audit.contract_version",
            ),
            report_id=_string(
                audit_value["report_id"], "derivation_audit.report_id"
            ),
            status=_enum(
                DerivationAuditStatus,
                audit_value["status"],
                "derivation_audit.status",
            ),
            scope=_enum(
                ReferenceEvidenceAuditScope,
                audit_value["scope"],
                "derivation_audit.scope",
            ),
            independently_revalidated=_boolean(
                audit_value["independently_revalidated"],
                "derivation_audit.independently_revalidated",
            ),
            processor_name=_string(
                audit_value["processor_name"],
                "derivation_audit.processor_name",
            ),
            processor_version=_string(
                audit_value["processor_version"],
                "derivation_audit.processor_version",
            ),
            audited_artifact_ids=_string_tuple(
                audit_value["audited_artifact_ids"],
                "derivation_audit.audited_artifact_ids",
                REFERENCE_EVIDENCE_MAX_LINEAGE_IDS,
            ),
            audited_layer_counts=_decode_layer_counts(
                audit_value["audited_layer_counts"]
            ),
            finding_count=_integer(
                audit_value["finding_count"],
                "derivation_audit.finding_count",
            ),
        ),
        limitations=_string_tuple(
            root["limitations"],
            "limitations",
            REFERENCE_EVIDENCE_MAX_LIMITATIONS,
        ),
    )


def _decode_artifact(value: object, name: str) -> ReferenceEvidenceArtifact:
    mapping = _mapping(value, name, {"media_type", "sha256", "byte_length"})
    return ReferenceEvidenceArtifact(
        media_type=_string(mapping["media_type"], f"{name}.media_type"),
        sha256=_string(mapping["sha256"], f"{name}.sha256"),
        byte_length=_integer(mapping["byte_length"], f"{name}.byte_length"),
    )


def _decode_layer_counts(
    value: object,
) -> tuple[ReferenceEvidenceLayerCount, ...]:
    values = _list(
        value,
        "derivation_audit.audited_layer_counts",
        REFERENCE_EVIDENCE_MAX_LAYER_COUNTS,
    )
    result: list[ReferenceEvidenceLayerCount] = []
    for index, item in enumerate(values):
        name = f"derivation_audit.audited_layer_counts[{index}]"
        mapping = _mapping(item, name, {"layer", "count"})
        result.append(
            ReferenceEvidenceLayerCount(
                layer=_string(mapping["layer"], f"{name}.layer"),
                count=_integer(mapping["count"], f"{name}.count"),
            )
        )
    return tuple(result)


def _mapping(value: object, name: str, fields: set[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    actual = set(value)
    unknown = actual - fields
    missing = fields - actual
    if unknown:
        raise ValueError(f"{name} has unknown fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"{name} is missing fields: {sorted(missing)}")
    if any(not isinstance(key, str) for key in value):
        raise TypeError(f"{name} field names must be strings")
    return value


def _list(value: object, name: str, maximum: int) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be an array")
    if len(value) > maximum:
        raise ReferenceEvidenceLimitError(f"{name} exceeds the item limit")
    return value


def _string(value: object, name: str) -> str:
    return _require_text(value, name)


def _integer(value: object, name: str) -> int:
    return _require_nonnegative_int(value, name)


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be boolean")
    return value


def _string_tuple(value: object, name: str, maximum: int) -> tuple[str, ...]:
    values = _list(value, name, maximum)
    return tuple(
        _string(item, f"{name}[{index}]") for index, item in enumerate(values)
    )


def _enum(enum_type: type[StrEnum], value: object, name: str) -> Any:
    text = _string(value, name)
    try:
        return enum_type(text)
    except ValueError as error:
        raise ValueError(f"{name} is unsupported: {text}") from error


def _object_without_duplicates(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object field: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"unsupported JSON constant: {value}")


def _require_bounded_json_nesting(text: str) -> None:
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > _MAX_JSON_DEPTH:
                raise ReferenceEvidenceLimitError(
                    "JSON nesting exceeds the depth limit"
                )
        elif character in "]}":
            depth -= 1
            if depth < 0:
                raise ValueError("JSON nesting is unbalanced")
    if in_string or depth != 0:
        raise ValueError("JSON nesting is incomplete")
