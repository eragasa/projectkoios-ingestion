from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum, StrEnum
from itertools import islice

from projectkoios.ingestion.equations import EquationCandidate
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import Metadata, WarningSeverity
from projectkoios.ingestion.pdf.models import RenderedRegion

EQUATION_TRANSCRIPTION_CONTRACT_VERSION = "1.0"
EQUATION_TRANSCRIPTION_CONFIGURATION_VERSION = "1"

_MAX_SELECTIONS = 256
_MAX_IMAGES = 256
_MAX_PIXELS_PER_IMAGE = 25_000_000
_MAX_BYTES_PER_IMAGE = 100_000_000
_MAX_TOTAL_PIXELS = 25_000_000
_MAX_TOTAL_IMAGE_BYTES = 100_000_000
_MAX_FORMATS = 2
_MAX_PROPOSALS_PER_SELECTION = 2
_MAX_OUTPUT_CHARACTERS_PER_PROPOSAL = 1_000_000
_MAX_SYMBOLS_PER_PROPOSAL = 100_000
_MAX_SYMBOL_TEXT_CHARACTERS = 65_536
_MAX_WARNINGS_PER_SELECTION = 1_024
_MAX_WARNING_MESSAGE_CHARACTERS = 65_536
_MAX_WARNING_EVIDENCE_ENTRIES = 256
_MAX_WARNING_EVIDENCE_CHARACTERS = 1_000_000
_MAX_FAILURE_MESSAGE_CHARACTERS = 65_536
_MAX_RESOURCES = 64
_MAX_IDENTITY_CHARACTERS = 4_096
_MAX_TOTAL_IDENTITY_CHARACTERS = 1_000_000
_MAX_TOTAL_OUTPUT_CHARACTERS = 5_000_000
_MAX_TOTAL_SYMBOLS = 100_000
_MAX_TOTAL_WARNINGS = 4_096
_MAX_RESULT_BYTES = 64_000_000


class EquationTranscriptionLimitError(ValueError):
    """Raised before a transcription contract exceeds a hard bound."""


class EquationTranscriptionFormat(StrEnum):
    LATEX = "latex"
    MATHML = "mathml"


class EquationTranscriptionStatus(StrEnum):
    """Adapter execution outcome, never acceptance or correctness."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class EquationSymbolStatus(StrEnum):
    """Proposal-only symbol status with no accepted state."""

    PROPOSED = "proposed"
    LOW_CONFIDENCE = "low_confidence"
    UNASSESSED = "unassessed"


class EquationSymbolConfidenceCoverage(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class EquationTranscriptionFailureKind(StrEnum):
    INPUT_REJECTED = "input_rejected"
    RESOURCE_LIMIT = "resource_limit"
    PROCESSOR_UNAVAILABLE = "processor_unavailable"
    PROCESSOR_ERROR = "processor_error"
    UNSUPPORTED_FORMAT = "unsupported_format"
    OUTPUT_INVALID = "output_invalid"
    OUTPUT_INCOMPLETE = "output_incomplete"


class EquationTranscriptionResourceIdentityKind(StrEnum):
    SHA256 = "sha256"
    EXPLICIT = "explicit"


@dataclass(frozen=True)
class EquationTranscriptionConfidence:
    """An adapter score with explicit method and scale semantics."""

    value: float
    method: str
    method_version: str
    scale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _unit_float("confidence", self.value))
        for name, value in (
            ("confidence method", self.method),
            ("confidence method version", self.method_version),
            ("confidence scale", self.scale),
        ):
            _bounded_string(name, value, nonempty=True)

    def identity_parts(self) -> tuple[object, ...]:
        return (self.value, self.method, self.method_version, self.scale)


@dataclass(frozen=True)
class EquationTranscriptionResourceIdentity:
    """An immutable backend model, vocabulary, or other resource identity."""

    resource_name: str
    identity_kind: EquationTranscriptionResourceIdentityKind
    resource_identity: str

    def __post_init__(self) -> None:
        _bounded_string("resource name", self.resource_name, nonempty=True)
        if not isinstance(
            self.identity_kind, EquationTranscriptionResourceIdentityKind
        ):
            raise TypeError("unsupported transcription resource identity kind")
        _bounded_string(
            "resource identity", self.resource_identity, nonempty=True
        )
        if (
            self.identity_kind
            is EquationTranscriptionResourceIdentityKind.SHA256
        ):
            _validate_sha256("resource identity", self.resource_identity)

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.resource_name,
            self.identity_kind.value,
            self.resource_identity,
        )


@dataclass(frozen=True)
class EquationTranscriptionProcessorIdentity:
    """Request-specific adapter, backend, and resource provenance."""

    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    resources: tuple[EquationTranscriptionResourceIdentity, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("processor name", self.processor_name),
            ("processor version", self.processor_version),
            ("backend name", self.backend_name),
            ("backend version", self.backend_version),
        ):
            _bounded_string(name, value, nonempty=True)
        _require_tuple("resources", self.resources)
        if len(self.resources) > _MAX_RESOURCES:
            raise EquationTranscriptionLimitError(
                "too many resource identities"
            )
        for resource in self.resources:
            if not isinstance(resource, EquationTranscriptionResourceIdentity):
                raise TypeError("resources contain an unsupported value")
        names = tuple(resource.resource_name for resource in self.resources)
        if len(set(names)) != len(names):
            raise ValueError("resource names must be unique")
        if names != tuple(sorted(names)):
            raise ValueError("resource identities must be ordered by name")

    @property
    def identity_digest(self) -> str:
        return stable_id(
            "equation-transcription-processor", self.identity_parts()
        )

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
            tuple(resource.identity_parts() for resource in self.resources),
        )


@dataclass(frozen=True)
class EquationTranscriptionConfiguration:
    """Requested formats, uncertainty threshold, and resource bounds."""

    configuration_version: str = EQUATION_TRANSCRIPTION_CONFIGURATION_VERSION
    formats: tuple[EquationTranscriptionFormat, ...] = (
        EquationTranscriptionFormat.LATEX,
    )
    low_confidence_threshold: float = 0.75
    max_selections: int = _MAX_SELECTIONS
    max_images: int = _MAX_IMAGES
    max_pixels_per_image: int = _MAX_PIXELS_PER_IMAGE
    max_bytes_per_image: int = _MAX_BYTES_PER_IMAGE
    max_total_pixels: int = _MAX_TOTAL_PIXELS
    max_total_image_bytes: int = _MAX_TOTAL_IMAGE_BYTES
    max_formats: int = _MAX_FORMATS
    max_proposals_per_selection: int = _MAX_PROPOSALS_PER_SELECTION
    max_output_characters_per_proposal: int = (
        _MAX_OUTPUT_CHARACTERS_PER_PROPOSAL
    )
    max_symbols_per_proposal: int = _MAX_SYMBOLS_PER_PROPOSAL
    max_symbol_text_characters: int = _MAX_SYMBOL_TEXT_CHARACTERS
    max_warnings_per_selection: int = _MAX_WARNINGS_PER_SELECTION
    max_warning_message_characters: int = _MAX_WARNING_MESSAGE_CHARACTERS
    max_warning_evidence_entries: int = _MAX_WARNING_EVIDENCE_ENTRIES
    max_warning_evidence_characters: int = _MAX_WARNING_EVIDENCE_CHARACTERS
    max_failure_message_characters: int = _MAX_FAILURE_MESSAGE_CHARACTERS
    max_resources: int = _MAX_RESOURCES
    max_identity_characters: int = _MAX_IDENTITY_CHARACTERS
    max_total_identity_characters: int = _MAX_TOTAL_IDENTITY_CHARACTERS
    max_total_output_characters: int = _MAX_TOTAL_OUTPUT_CHARACTERS
    max_total_symbols: int = _MAX_TOTAL_SYMBOLS
    max_total_warnings: int = _MAX_TOTAL_WARNINGS
    max_result_bytes: int = _MAX_RESULT_BYTES

    def __post_init__(self) -> None:
        if (
            self.configuration_version
            != EQUATION_TRANSCRIPTION_CONFIGURATION_VERSION
        ):
            raise ValueError("unsupported transcription configuration version")
        _require_tuple("formats", self.formats)
        if not self.formats:
            raise ValueError("formats must be non-empty")
        if any(
            not isinstance(item, EquationTranscriptionFormat)
            for item in self.formats
        ):
            raise TypeError("formats contain an unsupported value")
        if len(set(self.formats)) != len(self.formats):
            raise ValueError("formats must be unique")
        integer_limits = (
            ("max_selections", _MAX_SELECTIONS),
            ("max_images", _MAX_IMAGES),
            ("max_pixels_per_image", _MAX_PIXELS_PER_IMAGE),
            ("max_bytes_per_image", _MAX_BYTES_PER_IMAGE),
            ("max_total_pixels", _MAX_TOTAL_PIXELS),
            ("max_total_image_bytes", _MAX_TOTAL_IMAGE_BYTES),
            ("max_formats", _MAX_FORMATS),
            ("max_proposals_per_selection", _MAX_PROPOSALS_PER_SELECTION),
            (
                "max_output_characters_per_proposal",
                _MAX_OUTPUT_CHARACTERS_PER_PROPOSAL,
            ),
            ("max_symbols_per_proposal", _MAX_SYMBOLS_PER_PROPOSAL),
            ("max_symbol_text_characters", _MAX_SYMBOL_TEXT_CHARACTERS),
            ("max_warnings_per_selection", _MAX_WARNINGS_PER_SELECTION),
            (
                "max_warning_message_characters",
                _MAX_WARNING_MESSAGE_CHARACTERS,
            ),
            (
                "max_warning_evidence_entries",
                _MAX_WARNING_EVIDENCE_ENTRIES,
            ),
            (
                "max_warning_evidence_characters",
                _MAX_WARNING_EVIDENCE_CHARACTERS,
            ),
            (
                "max_failure_message_characters",
                _MAX_FAILURE_MESSAGE_CHARACTERS,
            ),
            ("max_resources", _MAX_RESOURCES),
            ("max_identity_characters", _MAX_IDENTITY_CHARACTERS),
            (
                "max_total_identity_characters",
                _MAX_TOTAL_IDENTITY_CHARACTERS,
            ),
            ("max_total_output_characters", _MAX_TOTAL_OUTPUT_CHARACTERS),
            ("max_total_symbols", _MAX_TOTAL_SYMBOLS),
            ("max_total_warnings", _MAX_TOTAL_WARNINGS),
            ("max_result_bytes", _MAX_RESULT_BYTES),
        )
        for name, hard_maximum in integer_limits:
            value = getattr(self, name)
            _positive_integer(name, value)
            if value > hard_maximum:
                raise EquationTranscriptionLimitError(
                    f"{name} exceeds its implementation maximum "
                    f"({hard_maximum})"
                )
        if len(self.formats) > self.max_formats:
            raise EquationTranscriptionLimitError(
                "format count exceeds max_formats"
            )
        object.__setattr__(
            self,
            "low_confidence_threshold",
            _unit_float(
                "low_confidence_threshold", self.low_confidence_threshold
            ),
        )

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "equation-transcription-configuration", self.identity_parts()
        )

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, tuple(item.value for item in value))
            if name == "formats"
            else (name, value)
            for name in self.__dataclass_fields__
            for value in (getattr(self, name),)
        )


@dataclass(frozen=True)
class EquationTranscriptionSelection:
    """One exact equation candidate and its retained source image."""

    selection_id: str
    candidate: EquationCandidate
    contract_version: str = EQUATION_TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def from_candidate(
        cls, candidate: EquationCandidate
    ) -> EquationTranscriptionSelection:
        if not isinstance(candidate, EquationCandidate):
            raise TypeError("candidate must be an EquationCandidate")
        _validate_candidate_region(candidate)
        return cls(
            selection_id=_selection_id(candidate),
            candidate=candidate,
        )

    @property
    def rendered_region(self) -> RenderedRegion:
        return self.candidate.rendered_region

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported transcription selection version")
        if not isinstance(self.candidate, EquationCandidate):
            raise TypeError("candidate must be an EquationCandidate")
        _validate_candidate_region(self.candidate)
        _bounded_string("selection ID", self.selection_id, nonempty=True)
        if self.selection_id != _selection_id(self.candidate):
            raise ValueError("selection ID does not match equation evidence")

    def identity_parts(self) -> tuple[object, ...]:
        candidate = self.candidate
        region = candidate.rendered_region
        return (
            self.selection_id,
            candidate.contract_version,
            candidate.candidate_id,
            candidate.warning_ids,
            region.region_id,
            region.source_id,
            region.source_blob_id,
            region.source_content_hash,
            region.page_index,
            region.content_sha256,
        )


@dataclass(frozen=True)
class EquationTranscriptionRequest:
    """A non-empty ordered request retaining every exact source candidate."""

    request_id: str
    selections: tuple[EquationTranscriptionSelection, ...]
    configuration: EquationTranscriptionConfiguration
    contract_version: str = EQUATION_TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        selections: Iterable[EquationTranscriptionSelection],
        *,
        configuration: EquationTranscriptionConfiguration | None = None,
    ) -> EquationTranscriptionRequest:
        actual = configuration or EquationTranscriptionConfiguration()
        bounded = tuple(islice(selections, actual.max_selections + 1))
        if len(bounded) > actual.max_selections:
            raise EquationTranscriptionLimitError(
                "selection count exceeds max_selections"
            )
        _validate_request_parts(bounded, actual)
        return cls(
            request_id=_request_id(bounded, actual),
            selections=bounded,
            configuration=actual,
        )

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported transcription request version")
        _bounded_string("request ID", self.request_id, nonempty=True)
        _validate_request_parts(self.selections, self.configuration)
        if self.request_id != _request_id(self.selections, self.configuration):
            raise ValueError("request ID does not match transcription evidence")


@dataclass(frozen=True)
class EquationTranscriptionWarning:
    """Stable selection-local uncertainty evidence from an adapter."""

    warning_id: str
    selection_id: str
    output_format: EquationTranscriptionFormat | None
    code: str
    severity: WarningSeverity
    message: str
    evidence: Metadata = ()
    contract_version: str = EQUATION_TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        code: str,
        severity: WarningSeverity,
        message: str,
        output_format: EquationTranscriptionFormat | None = None,
        evidence: Metadata = (),
    ) -> EquationTranscriptionWarning:
        _validate_warning_parts(
            selection_id,
            output_format,
            code,
            severity,
            message,
            evidence,
        )
        return cls(
            warning_id=_warning_id(
                selection_id,
                output_format,
                code,
                severity,
                message,
                evidence,
            ),
            selection_id=selection_id,
            output_format=output_format,
            code=code,
            severity=severity,
            message=message,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported transcription warning version")
        _validate_warning_parts(
            self.selection_id,
            self.output_format,
            self.code,
            self.severity,
            self.message,
            self.evidence,
        )
        if self.warning_id != _warning_id(
            self.selection_id,
            self.output_format,
            self.code,
            self.severity,
            self.message,
            self.evidence,
        ):
            raise ValueError("warning ID does not match its evidence")


@dataclass(frozen=True)
class EquationTranscriptionFailure:
    """Typed failure evidence for a partial or failed selection."""

    failure_id: str
    selection_id: str
    kind: EquationTranscriptionFailureKind
    message: str
    retryable: bool
    warning_ids: tuple[str, ...]
    contract_version: str = EQUATION_TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        kind: EquationTranscriptionFailureKind,
        message: str,
        retryable: bool,
        warning_ids: tuple[str, ...],
    ) -> EquationTranscriptionFailure:
        _validate_failure_parts(
            selection_id, kind, message, retryable, warning_ids
        )
        return cls(
            failure_id=_failure_id(
                selection_id, kind, message, retryable, warning_ids
            ),
            selection_id=selection_id,
            kind=kind,
            message=message,
            retryable=retryable,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported transcription failure version")
        _validate_failure_parts(
            self.selection_id,
            self.kind,
            self.message,
            self.retryable,
            self.warning_ids,
        )
        if self.failure_id != _failure_id(
            self.selection_id,
            self.kind,
            self.message,
            self.retryable,
            self.warning_ids,
        ):
            raise ValueError("failure ID does not match its evidence")


@dataclass(frozen=True)
class EquationTranscriptionSymbol:
    """One exact output substring with explicit uncertainty semantics."""

    symbol_id: str
    selection_id: str
    output_format: EquationTranscriptionFormat
    start_offset: int
    end_offset: int
    text: str
    confidence: EquationTranscriptionConfidence | None
    status: EquationSymbolStatus
    warning_ids: tuple[str, ...]
    configuration_digest: str
    processor_identity_digest: str
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    contract_version: str = EQUATION_TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        output_format: EquationTranscriptionFormat,
        start_offset: int,
        end_offset: int,
        text: str,
        confidence: EquationTranscriptionConfidence | None,
        warning_ids: tuple[str, ...],
        configuration: EquationTranscriptionConfiguration,
        processor_identity: EquationTranscriptionProcessorIdentity,
    ) -> EquationTranscriptionSymbol:
        status = _symbol_status(confidence, configuration)
        _validate_symbol_parts(
            selection_id=selection_id,
            output_format=output_format,
            start_offset=start_offset,
            end_offset=end_offset,
            text=text,
            confidence=confidence,
            status=status,
            warning_ids=warning_ids,
            configuration_digest=configuration.configuration_digest,
            processor_identity=processor_identity,
            max_text_characters=configuration.max_symbol_text_characters,
        )
        symbol_id = _symbol_id(
            selection_id,
            output_format,
            start_offset,
            end_offset,
            text,
            confidence,
            status,
            warning_ids,
            configuration.configuration_digest,
            processor_identity,
        )
        return cls(
            symbol_id=symbol_id,
            selection_id=selection_id,
            output_format=output_format,
            start_offset=start_offset,
            end_offset=end_offset,
            text=text,
            confidence=confidence,
            status=status,
            warning_ids=warning_ids,
            configuration_digest=configuration.configuration_digest,
            processor_identity_digest=processor_identity.identity_digest,
            processor_name=processor_identity.processor_name,
            processor_version=processor_identity.processor_version,
            backend_name=processor_identity.backend_name,
            backend_version=processor_identity.backend_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported transcription symbol version")
        _bounded_string(
            "symbol processor identity digest",
            self.processor_identity_digest,
            nonempty=True,
        )
        identity = _identity_from_output(self)
        _validate_symbol_parts(
            selection_id=self.selection_id,
            output_format=self.output_format,
            start_offset=self.start_offset,
            end_offset=self.end_offset,
            text=self.text,
            confidence=self.confidence,
            status=self.status,
            warning_ids=self.warning_ids,
            configuration_digest=self.configuration_digest,
            processor_identity=identity,
            max_text_characters=_MAX_SYMBOL_TEXT_CHARACTERS,
        )
        if self.symbol_id != _symbol_id(
            self.selection_id,
            self.output_format,
            self.start_offset,
            self.end_offset,
            self.text,
            self.confidence,
            self.status,
            self.warning_ids,
            self.configuration_digest,
            identity,
            processor_identity_digest=self.processor_identity_digest,
        ):
            raise ValueError("symbol ID does not match its evidence")


@dataclass(frozen=True)
class EquationTranscriptionProposal:
    """One unaccepted LaTeX or MathML proposal for one source image."""

    proposal_id: str
    selection_id: str
    candidate_id: str
    rendered_region_id: str
    output_format: EquationTranscriptionFormat
    text: str
    confidence: EquationTranscriptionConfidence | None
    symbol_confidence_coverage: EquationSymbolConfidenceCoverage
    symbols: tuple[EquationTranscriptionSymbol, ...]
    warning_ids: tuple[str, ...]
    configuration_digest: str
    processor_identity_digest: str
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    contract_version: str = EQUATION_TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection: EquationTranscriptionSelection,
        output_format: EquationTranscriptionFormat,
        text: str,
        confidence: EquationTranscriptionConfidence | None,
        symbol_confidence_coverage: EquationSymbolConfidenceCoverage,
        symbols: tuple[EquationTranscriptionSymbol, ...],
        warning_ids: tuple[str, ...],
        configuration: EquationTranscriptionConfiguration,
        processor_identity: EquationTranscriptionProcessorIdentity,
    ) -> EquationTranscriptionProposal:
        _validate_proposal_parts(
            selection=selection,
            output_format=output_format,
            text=text,
            confidence=confidence,
            coverage=symbol_confidence_coverage,
            symbols=symbols,
            warning_ids=warning_ids,
            configuration=configuration,
            processor_identity=processor_identity,
        )
        proposal_id = _proposal_id(
            selection,
            output_format,
            text,
            confidence,
            symbol_confidence_coverage,
            symbols,
            warning_ids,
            configuration.configuration_digest,
            processor_identity,
        )
        return cls(
            proposal_id=proposal_id,
            selection_id=selection.selection_id,
            candidate_id=selection.candidate.candidate_id,
            rendered_region_id=selection.rendered_region.region_id,
            output_format=output_format,
            text=text,
            confidence=confidence,
            symbol_confidence_coverage=symbol_confidence_coverage,
            symbols=symbols,
            warning_ids=warning_ids,
            configuration_digest=configuration.configuration_digest,
            processor_identity_digest=processor_identity.identity_digest,
            processor_name=processor_identity.processor_name,
            processor_version=processor_identity.processor_version,
            backend_name=processor_identity.backend_name,
            backend_version=processor_identity.backend_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported transcription proposal version")
        _bounded_string("proposal ID", self.proposal_id, nonempty=True)
        _bounded_string(
            "proposal selection ID", self.selection_id, nonempty=True
        )
        _bounded_string(
            "proposal candidate ID", self.candidate_id, nonempty=True
        )
        _bounded_string(
            "proposal region ID", self.rendered_region_id, nonempty=True
        )
        if not isinstance(self.output_format, EquationTranscriptionFormat):
            raise TypeError("proposal output format is unsupported")
        _bounded_string(
            "proposal text",
            self.text,
            nonempty=True,
            limit=_MAX_OUTPUT_CHARACTERS_PER_PROPOSAL,
        )
        _validate_confidence(self.confidence)
        if not isinstance(
            self.symbol_confidence_coverage,
            EquationSymbolConfidenceCoverage,
        ):
            raise TypeError("symbol confidence coverage is unsupported")
        _require_tuple("proposal symbols", self.symbols)
        _require_unique_strings("proposal warning IDs", self.warning_ids)
        _bounded_string(
            "proposal processor identity digest",
            self.processor_identity_digest,
            nonempty=True,
        )
        identity = _identity_from_output(self)
        _validate_symbol_ranges(
            self.text,
            self.output_format,
            self.symbols,
            self.symbol_confidence_coverage,
            self.warning_ids,
            _MAX_SYMBOLS_PER_PROPOSAL,
        )
        if self.confidence is None and not self.warning_ids:
            raise ValueError(
                "unassessed proposal confidence requires a warning"
            )
        for symbol in self.symbols:
            _same_output_identity(self, symbol)
            if symbol.configuration_digest != self.configuration_digest:
                raise ValueError("symbol configuration does not match proposal")
        expected = _proposal_id_from_parts(
            self.selection_id,
            self.candidate_id,
            self.rendered_region_id,
            self.output_format,
            self.text,
            self.confidence,
            self.symbol_confidence_coverage,
            self.symbols,
            self.warning_ids,
            self.configuration_digest,
            identity,
            processor_identity_digest=self.processor_identity_digest,
        )
        if self.proposal_id != expected:
            raise ValueError("proposal ID does not match its evidence")


@dataclass(frozen=True)
class EquationTranscriptionSelectionResult:
    """Completed, partial, or failed output for one exact selection."""

    selection_result_id: str
    selection_id: str
    candidate_id: str
    rendered_region_id: str
    status: EquationTranscriptionStatus
    proposals: tuple[EquationTranscriptionProposal, ...]
    warnings: tuple[EquationTranscriptionWarning, ...]
    failure: EquationTranscriptionFailure | None
    configuration_digest: str
    processor_identity_digest: str
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    contract_version: str = EQUATION_TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection: EquationTranscriptionSelection,
        configuration: EquationTranscriptionConfiguration,
        status: EquationTranscriptionStatus,
        proposals: tuple[EquationTranscriptionProposal, ...] = (),
        warnings: tuple[EquationTranscriptionWarning, ...] = (),
        failure: EquationTranscriptionFailure | None = None,
        processor_identity: EquationTranscriptionProcessorIdentity,
    ) -> EquationTranscriptionSelectionResult:
        _preflight_selection_result_creation(
            selection,
            configuration,
            status,
            proposals,
            warnings,
            failure,
            processor_identity,
        )
        result = cls(
            selection_result_id=_selection_result_id(
                selection,
                status,
                proposals,
                warnings,
                failure,
                configuration.configuration_digest,
                processor_identity,
            ),
            selection_id=selection.selection_id,
            candidate_id=selection.candidate.candidate_id,
            rendered_region_id=selection.rendered_region.region_id,
            status=status,
            proposals=proposals,
            warnings=warnings,
            failure=failure,
            configuration_digest=configuration.configuration_digest,
            processor_identity_digest=processor_identity.identity_digest,
            processor_name=processor_identity.processor_name,
            processor_version=processor_identity.processor_version,
            backend_name=processor_identity.backend_name,
            backend_version=processor_identity.backend_version,
        )
        _validate_selection_result(result, selection, configuration)
        return result

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError(
                "unsupported transcription selection-result version"
            )
        _bounded_string(
            "selection result ID", self.selection_result_id, nonempty=True
        )
        for name, value in (
            ("selection ID", self.selection_id),
            ("candidate ID", self.candidate_id),
            ("rendered region ID", self.rendered_region_id),
            ("configuration digest", self.configuration_digest),
            ("processor identity digest", self.processor_identity_digest),
        ):
            _bounded_string(name, value, nonempty=True)
        if not isinstance(self.status, EquationTranscriptionStatus):
            raise TypeError("transcription selection status is unsupported")
        _require_tuple("proposals", self.proposals)
        _require_tuple("warnings", self.warnings)
        identity = _identity_from_output(self)
        _validate_selection_result_intrinsic(self, identity)
        expected = _selection_result_id_from_parts(
            self.selection_id,
            self.candidate_id,
            self.rendered_region_id,
            self.status,
            self.proposals,
            self.warnings,
            self.failure,
            self.configuration_digest,
            identity,
            processor_identity_digest=self.processor_identity_digest,
        )
        if self.selection_result_id != expected:
            raise ValueError("selection-result ID does not match its evidence")


@dataclass(frozen=True)
class EquationTranscriptionResult:
    """Ordered adapter outcomes retaining exact source images and provenance."""

    result_id: str
    request: EquationTranscriptionRequest
    selection_results: tuple[EquationTranscriptionSelectionResult, ...]
    status: EquationTranscriptionStatus
    cache_key: str
    processor_identity: EquationTranscriptionProcessorIdentity
    contract_version: str = EQUATION_TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: EquationTranscriptionRequest,
        selection_results: tuple[EquationTranscriptionSelectionResult, ...],
        processor_identity: EquationTranscriptionProcessorIdentity,
    ) -> EquationTranscriptionResult:
        _preflight_result(request, selection_results, processor_identity)
        status = _overall_status(selection_results)
        cache_key = build_equation_transcription_cache_key(
            request=request,
            processor_identity=processor_identity,
        )
        _validate_contract_size(
            (request, selection_results, status, cache_key, processor_identity),
            request.configuration.max_result_bytes,
        )
        return cls(
            result_id=_result_id(
                request,
                selection_results,
                status,
                cache_key,
                processor_identity,
            ),
            request=request,
            selection_results=selection_results,
            status=status,
            cache_key=cache_key,
            processor_identity=processor_identity,
        )

    @property
    def processor_name(self) -> str:
        return self.processor_identity.processor_name

    @property
    def processor_version(self) -> str:
        return self.processor_identity.processor_version

    @property
    def backend_name(self) -> str:
        return self.processor_identity.backend_name

    @property
    def backend_version(self) -> str:
        return self.processor_identity.backend_version

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported transcription result version")
        _preflight_result(
            self.request, self.selection_results, self.processor_identity
        )
        for selection, result in zip(
            self.request.selections, self.selection_results, strict=True
        ):
            _validate_selection_result(
                result, selection, self.request.configuration
            )
        expected_status = _overall_status(self.selection_results)
        if self.status is not expected_status:
            raise ValueError("result status contradicts selection statuses")
        expected_cache_key = build_equation_transcription_cache_key(
            request=self.request,
            processor_identity=self.processor_identity,
        )
        if self.cache_key != expected_cache_key:
            raise ValueError("cache key does not match transcription evidence")
        _validate_contract_size(
            self, self.request.configuration.max_result_bytes
        )
        expected_id = _result_id(
            self.request,
            self.selection_results,
            self.status,
            self.cache_key,
            self.processor_identity,
        )
        if self.result_id != expected_id:
            raise ValueError("result ID does not match transcription evidence")


def build_equation_transcription_cache_key(
    *,
    request: EquationTranscriptionRequest,
    processor_identity: EquationTranscriptionProcessorIdentity,
    contract_version: str = EQUATION_TRANSCRIPTION_CONTRACT_VERSION,
) -> str:
    """Build a complete derived-cache identity without storing a result."""
    if not isinstance(request, EquationTranscriptionRequest):
        raise TypeError("request must be an EquationTranscriptionRequest")
    if not isinstance(
        processor_identity, EquationTranscriptionProcessorIdentity
    ):
        raise TypeError(
            "processor_identity must be an "
            "EquationTranscriptionProcessorIdentity"
        )
    _bounded_string("contract version", contract_version, nonempty=True)
    _validate_processor_identity(processor_identity, request.configuration)
    _validate_identity_size(
        (
            contract_version,
            tuple(
                selection.identity_parts() for selection in request.selections
            ),
            request.configuration.identity_parts(),
            processor_identity.identity_parts(),
        ),
        request.configuration.max_total_identity_characters,
    )
    return stable_id(
        "equation-transcription-cache",
        contract_version,
        tuple(selection.identity_parts() for selection in request.selections),
        request.configuration.identity_parts(),
        processor_identity.identity_parts(),
    )


def _selection_id(candidate: EquationCandidate) -> str:
    region = candidate.rendered_region
    return stable_id(
        "equation-transcription-selection",
        candidate.contract_version,
        candidate.candidate_id,
        candidate.warning_ids,
        region.region_id,
        region.content_sha256,
    )


def _request_id(
    selections: tuple[EquationTranscriptionSelection, ...],
    configuration: EquationTranscriptionConfiguration,
) -> str:
    return stable_id(
        "equation-transcription-request",
        tuple(selection.identity_parts() for selection in selections),
        configuration.identity_parts(),
    )


def _warning_id(
    selection_id: str,
    output_format: EquationTranscriptionFormat | None,
    code: str,
    severity: WarningSeverity,
    message: str,
    evidence: Metadata,
) -> str:
    return stable_id(
        "equation-transcription-warning",
        selection_id,
        output_format.value if output_format is not None else None,
        code,
        severity.value,
        message,
        evidence,
    )


def _failure_id(
    selection_id: str,
    kind: EquationTranscriptionFailureKind,
    message: str,
    retryable: bool,
    warning_ids: tuple[str, ...],
) -> str:
    return stable_id(
        "equation-transcription-failure",
        selection_id,
        kind.value,
        message,
        retryable,
        warning_ids,
    )


def _symbol_id(
    selection_id: str,
    output_format: EquationTranscriptionFormat,
    start_offset: int,
    end_offset: int,
    text: str,
    confidence: EquationTranscriptionConfidence | None,
    status: EquationSymbolStatus,
    warning_ids: tuple[str, ...],
    configuration_digest: str,
    processor_identity: EquationTranscriptionProcessorIdentity,
    *,
    processor_identity_digest: str | None = None,
) -> str:
    return stable_id(
        "equation-transcription-symbol",
        selection_id,
        output_format.value,
        start_offset,
        end_offset,
        text,
        confidence.identity_parts() if confidence is not None else None,
        status.value,
        warning_ids,
        configuration_digest,
        _output_processor_parts(processor_identity),
        processor_identity_digest or processor_identity.identity_digest,
    )


def _proposal_id(
    selection: EquationTranscriptionSelection,
    output_format: EquationTranscriptionFormat,
    text: str,
    confidence: EquationTranscriptionConfidence | None,
    coverage: EquationSymbolConfidenceCoverage,
    symbols: tuple[EquationTranscriptionSymbol, ...],
    warning_ids: tuple[str, ...],
    configuration_digest: str,
    processor_identity: EquationTranscriptionProcessorIdentity,
) -> str:
    return _proposal_id_from_parts(
        selection.selection_id,
        selection.candidate.candidate_id,
        selection.rendered_region.region_id,
        output_format,
        text,
        confidence,
        coverage,
        symbols,
        warning_ids,
        configuration_digest,
        processor_identity,
    )


def _proposal_id_from_parts(
    selection_id: str,
    candidate_id: str,
    rendered_region_id: str,
    output_format: EquationTranscriptionFormat,
    text: str,
    confidence: EquationTranscriptionConfidence | None,
    coverage: EquationSymbolConfidenceCoverage,
    symbols: tuple[EquationTranscriptionSymbol, ...],
    warning_ids: tuple[str, ...],
    configuration_digest: str,
    processor_identity: EquationTranscriptionProcessorIdentity,
    *,
    processor_identity_digest: str | None = None,
) -> str:
    return stable_id(
        "equation-transcription-proposal",
        selection_id,
        candidate_id,
        rendered_region_id,
        output_format.value,
        text,
        confidence.identity_parts() if confidence is not None else None,
        coverage.value,
        tuple(symbol.symbol_id for symbol in symbols),
        warning_ids,
        configuration_digest,
        _output_processor_parts(processor_identity),
        processor_identity_digest or processor_identity.identity_digest,
    )


def _selection_result_id(
    selection: EquationTranscriptionSelection,
    status: EquationTranscriptionStatus,
    proposals: tuple[EquationTranscriptionProposal, ...],
    warnings: tuple[EquationTranscriptionWarning, ...],
    failure: EquationTranscriptionFailure | None,
    configuration_digest: str,
    processor_identity: EquationTranscriptionProcessorIdentity,
    *,
    processor_identity_digest: str | None = None,
) -> str:
    return _selection_result_id_from_parts(
        selection.selection_id,
        selection.candidate.candidate_id,
        selection.rendered_region.region_id,
        status,
        proposals,
        warnings,
        failure,
        configuration_digest,
        processor_identity,
        processor_identity_digest=processor_identity_digest,
    )


def _selection_result_id_from_parts(
    selection_id: str,
    candidate_id: str,
    rendered_region_id: str,
    status: EquationTranscriptionStatus,
    proposals: tuple[EquationTranscriptionProposal, ...],
    warnings: tuple[EquationTranscriptionWarning, ...],
    failure: EquationTranscriptionFailure | None,
    configuration_digest: str,
    processor_identity: EquationTranscriptionProcessorIdentity,
    *,
    processor_identity_digest: str | None = None,
) -> str:
    return stable_id(
        "equation-transcription-selection-result",
        selection_id,
        candidate_id,
        rendered_region_id,
        status.value,
        tuple(proposal.proposal_id for proposal in proposals),
        tuple(warning.warning_id for warning in warnings),
        failure.failure_id if failure is not None else None,
        configuration_digest,
        _output_processor_parts(processor_identity),
        processor_identity_digest or processor_identity.identity_digest,
    )


def _result_id(
    request: EquationTranscriptionRequest,
    selection_results: tuple[EquationTranscriptionSelectionResult, ...],
    status: EquationTranscriptionStatus,
    cache_key: str,
    processor_identity: EquationTranscriptionProcessorIdentity,
) -> str:
    return stable_id(
        "equation-transcription-result",
        request.request_id,
        tuple(item.selection_result_id for item in selection_results),
        status.value,
        cache_key,
        processor_identity.identity_parts(),
    )


def _validate_candidate_region(candidate: EquationCandidate) -> None:
    region = candidate.rendered_region
    selected = region.source_bounding_box
    if not candidate.source_spans:
        raise ValueError("transcription candidate has no source spans")
    for span in candidate.source_spans:
        if (
            span.source_id != region.source_id
            or span.source_blob_id != region.source_blob_id
            or span.page_index != region.page_index
        ):
            raise ValueError(
                "equation candidate does not match its rendered source image"
            )
        box = span.bounding_box
        if box is None:
            raise ValueError(
                "equation candidate lacks rendered source geometry"
            )
        if not (
            selected[0] <= box[0]
            and selected[1] <= box[1]
            and selected[2] >= box[2]
            and selected[3] >= box[3]
        ):
            raise ValueError(
                "rendered source image does not contain candidate geometry"
            )


def _validate_request_parts(
    selections: tuple[EquationTranscriptionSelection, ...],
    configuration: EquationTranscriptionConfiguration,
) -> None:
    _require_tuple("selections", selections)
    if not isinstance(configuration, EquationTranscriptionConfiguration):
        raise TypeError(
            "configuration must be an EquationTranscriptionConfiguration"
        )
    if not selections:
        raise ValueError("transcription request must contain a selection")
    if len(selections) > configuration.max_selections:
        raise EquationTranscriptionLimitError(
            "selection count exceeds max_selections"
        )
    if any(
        not isinstance(selection, EquationTranscriptionSelection)
        for selection in selections
    ):
        raise TypeError("selections contain an unsupported value")
    selection_ids = tuple(selection.selection_id for selection in selections)
    candidate_ids = tuple(
        selection.candidate.candidate_id for selection in selections
    )
    if len(set(selection_ids)) != len(selection_ids):
        raise ValueError("selection IDs must be unique")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("equation candidates must be selected at most once")
    regions: dict[str, RenderedRegion] = {}
    for selection in selections:
        region = selection.rendered_region
        if region.byte_length > configuration.max_bytes_per_image:
            raise EquationTranscriptionLimitError(
                "source image exceeds max_bytes_per_image"
            )
        pixels = region.width_pixels * region.height_pixels
        if pixels > configuration.max_pixels_per_image:
            raise EquationTranscriptionLimitError(
                "source image exceeds max_pixels_per_image"
            )
        existing = regions.get(region.region_id)
        if existing is not None and existing != region:
            raise ValueError("one region ID resolves to inconsistent images")
        regions[region.region_id] = region
    if len(regions) > configuration.max_images:
        raise EquationTranscriptionLimitError("image count exceeds max_images")
    if sum(region.byte_length for region in regions.values()) > (
        configuration.max_total_image_bytes
    ):
        raise EquationTranscriptionLimitError(
            "source image bytes exceed max_total_image_bytes"
        )
    if (
        sum(
            region.width_pixels * region.height_pixels
            for region in regions.values()
        )
        > configuration.max_total_pixels
    ):
        raise EquationTranscriptionLimitError(
            "source image pixels exceed max_total_pixels"
        )
    _validate_identity_size(
        (
            tuple(selection.identity_parts() for selection in selections),
            configuration.identity_parts(),
        ),
        configuration.max_total_identity_characters,
    )


def _validate_warning_parts(
    selection_id: str,
    output_format: EquationTranscriptionFormat | None,
    code: str,
    severity: WarningSeverity,
    message: str,
    evidence: Metadata,
) -> None:
    _bounded_string("warning selection ID", selection_id, nonempty=True)
    if output_format is not None and not isinstance(
        output_format, EquationTranscriptionFormat
    ):
        raise TypeError("warning output format is unsupported")
    _bounded_string("warning code", code, nonempty=True)
    if not isinstance(severity, WarningSeverity):
        raise TypeError("warning severity is unsupported")
    _bounded_string(
        "warning message",
        message,
        nonempty=True,
        limit=_MAX_WARNING_MESSAGE_CHARACTERS,
    )
    _validate_metadata(evidence)


def _validate_failure_parts(
    selection_id: str,
    kind: EquationTranscriptionFailureKind,
    message: str,
    retryable: bool,
    warning_ids: tuple[str, ...],
) -> None:
    _bounded_string("failure selection ID", selection_id, nonempty=True)
    if not isinstance(kind, EquationTranscriptionFailureKind):
        raise TypeError("transcription failure kind is unsupported")
    _bounded_string(
        "failure message",
        message,
        nonempty=True,
        limit=_MAX_FAILURE_MESSAGE_CHARACTERS,
    )
    if not isinstance(retryable, bool):
        raise TypeError("failure retryable must be a boolean")
    _require_unique_strings("failure warning IDs", warning_ids, required=True)


def _validate_symbol_parts(
    *,
    selection_id: str,
    output_format: EquationTranscriptionFormat,
    start_offset: int,
    end_offset: int,
    text: str,
    confidence: EquationTranscriptionConfidence | None,
    status: EquationSymbolStatus,
    warning_ids: tuple[str, ...],
    configuration_digest: str,
    processor_identity: EquationTranscriptionProcessorIdentity,
    max_text_characters: int,
) -> None:
    _bounded_string("symbol selection ID", selection_id, nonempty=True)
    if not isinstance(output_format, EquationTranscriptionFormat):
        raise TypeError("symbol output format is unsupported")
    _nonnegative_integer("symbol start offset", start_offset)
    _nonnegative_integer("symbol end offset", end_offset)
    if end_offset <= start_offset:
        raise ValueError("symbol end offset must follow its start offset")
    _bounded_string(
        "symbol text",
        text,
        nonempty=True,
        limit=max_text_characters,
    )
    _validate_confidence(confidence)
    if not isinstance(status, EquationSymbolStatus):
        raise TypeError("symbol status is unsupported")
    _require_unique_strings("symbol warning IDs", warning_ids)
    if (
        status
        in (
            EquationSymbolStatus.LOW_CONFIDENCE,
            EquationSymbolStatus.UNASSESSED,
        )
        and not warning_ids
    ):
        raise ValueError("uncertain symbols require warning links")
    if status is EquationSymbolStatus.UNASSESSED and confidence is not None:
        raise ValueError("unassessed symbol must not carry confidence")
    if status is not EquationSymbolStatus.UNASSESSED and confidence is None:
        raise ValueError("assessed symbol requires confidence")
    _bounded_string(
        "symbol configuration digest", configuration_digest, nonempty=True
    )
    _validate_processor_identity(processor_identity, None)


def _validate_proposal_parts(
    *,
    selection: EquationTranscriptionSelection,
    output_format: EquationTranscriptionFormat,
    text: str,
    confidence: EquationTranscriptionConfidence | None,
    coverage: EquationSymbolConfidenceCoverage,
    symbols: tuple[EquationTranscriptionSymbol, ...],
    warning_ids: tuple[str, ...],
    configuration: EquationTranscriptionConfiguration,
    processor_identity: EquationTranscriptionProcessorIdentity,
) -> None:
    if not isinstance(selection, EquationTranscriptionSelection):
        raise TypeError("selection must be an EquationTranscriptionSelection")
    if output_format not in configuration.formats:
        raise ValueError("proposal format was not requested")
    _bounded_string(
        "proposal text",
        text,
        nonempty=True,
        limit=configuration.max_output_characters_per_proposal,
    )
    _validate_confidence(confidence)
    if not isinstance(coverage, EquationSymbolConfidenceCoverage):
        raise TypeError("symbol confidence coverage is unsupported")
    _require_tuple("symbols", symbols)
    _require_unique_strings("proposal warning IDs", warning_ids)
    if confidence is None and not warning_ids:
        raise ValueError("unassessed proposal confidence requires a warning")
    _validate_processor_identity(processor_identity, configuration)
    _validate_symbol_ranges(
        text,
        output_format,
        symbols,
        coverage,
        warning_ids,
        configuration.max_symbols_per_proposal,
    )
    for symbol in symbols:
        if symbol.selection_id != selection.selection_id:
            raise ValueError("symbol selection does not match proposal")
        if symbol.configuration_digest != configuration.configuration_digest:
            raise ValueError("symbol configuration does not match proposal")
        _same_output_identity_from_processor(symbol, processor_identity)
        expected_status = _symbol_status(symbol.confidence, configuration)
        if symbol.status is not expected_status:
            raise ValueError("symbol status contradicts confidence threshold")


def _validate_symbol_ranges(
    text: str,
    output_format: EquationTranscriptionFormat,
    symbols: tuple[EquationTranscriptionSymbol, ...],
    coverage: EquationSymbolConfidenceCoverage,
    proposal_warning_ids: tuple[str, ...],
    max_symbols: int,
) -> None:
    if len(symbols) > max_symbols:
        raise EquationTranscriptionLimitError(
            "symbol count exceeds max_symbols_per_proposal"
        )
    previous_end = 0
    uncovered_non_whitespace = False
    symbol_ids: set[str] = set()
    symbol_warning_ids: set[str] = set()
    has_unassessed_symbol = False
    for symbol in symbols:
        if not isinstance(symbol, EquationTranscriptionSymbol):
            raise TypeError("symbols contain an unsupported value")
        if symbol.symbol_id in symbol_ids:
            raise ValueError("symbol IDs must be unique")
        symbol_ids.add(symbol.symbol_id)
        if symbol.output_format is not output_format:
            raise ValueError("symbol output format does not match proposal")
        if symbol.start_offset < previous_end:
            raise ValueError(
                "symbol ranges must be ordered and non-overlapping"
            )
        if symbol.end_offset > len(text):
            raise ValueError("symbol range exceeds proposal text")
        if text[symbol.start_offset : symbol.end_offset] != symbol.text:
            raise ValueError(
                "symbol text does not match its exact output range"
            )
        if any(
            not character.isspace()
            for character in text[previous_end : symbol.start_offset]
        ):
            uncovered_non_whitespace = True
        previous_end = symbol.end_offset
        symbol_warning_ids.update(symbol.warning_ids)
        has_unassessed_symbol = (
            has_unassessed_symbol
            or symbol.status is EquationSymbolStatus.UNASSESSED
        )
    if any(not character.isspace() for character in text[previous_end:]):
        uncovered_non_whitespace = True
    if not symbol_warning_ids.issubset(set(proposal_warning_ids)):
        raise ValueError("symbol warnings must also link from the proposal")
    if coverage is EquationSymbolConfidenceCoverage.UNAVAILABLE:
        if symbols:
            raise ValueError(
                "unavailable symbol confidence cannot include symbols"
            )
        if not proposal_warning_ids:
            raise ValueError("unavailable symbol confidence requires a warning")
    elif coverage is EquationSymbolConfidenceCoverage.COMPLETE:
        if not symbols or uncovered_non_whitespace or has_unassessed_symbol:
            raise ValueError(
                "complete symbol confidence must assess all output text"
            )
    else:
        if not symbols or (
            not uncovered_non_whitespace and not has_unassessed_symbol
        ):
            raise ValueError(
                "partial symbol confidence must leave output unassessed"
            )


def _preflight_selection_result_creation(
    selection: EquationTranscriptionSelection,
    configuration: EquationTranscriptionConfiguration,
    status: EquationTranscriptionStatus,
    proposals: tuple[EquationTranscriptionProposal, ...],
    warnings: tuple[EquationTranscriptionWarning, ...],
    failure: EquationTranscriptionFailure | None,
    processor_identity: EquationTranscriptionProcessorIdentity,
) -> None:
    if not isinstance(selection, EquationTranscriptionSelection):
        raise TypeError("selection must be an EquationTranscriptionSelection")
    if not isinstance(configuration, EquationTranscriptionConfiguration):
        raise TypeError(
            "configuration must be an EquationTranscriptionConfiguration"
        )
    if not isinstance(status, EquationTranscriptionStatus):
        raise TypeError("transcription selection status is unsupported")
    _require_tuple("proposals", proposals)
    _require_tuple("warnings", warnings)
    if len(proposals) > configuration.max_proposals_per_selection:
        raise EquationTranscriptionLimitError(
            "proposal count exceeds max_proposals_per_selection"
        )
    if len(warnings) > configuration.max_warnings_per_selection:
        raise EquationTranscriptionLimitError(
            "warning count exceeds max_warnings_per_selection"
        )
    if any(
        not isinstance(proposal, EquationTranscriptionProposal)
        for proposal in proposals
    ):
        raise TypeError("proposals contain an unsupported value")
    if any(
        not isinstance(warning, EquationTranscriptionWarning)
        for warning in warnings
    ):
        raise TypeError("warnings contain an unsupported value")
    if failure is not None and not isinstance(
        failure, EquationTranscriptionFailure
    ):
        raise TypeError("failure has an unsupported value")
    _validate_processor_identity(processor_identity, configuration)


def _validate_selection_result_intrinsic(
    result: EquationTranscriptionSelectionResult,
    processor_identity: EquationTranscriptionProcessorIdentity,
) -> None:
    if len(result.proposals) > _MAX_PROPOSALS_PER_SELECTION:
        raise EquationTranscriptionLimitError("too many proposals")
    if len(result.warnings) > _MAX_WARNINGS_PER_SELECTION:
        raise EquationTranscriptionLimitError("too many warnings")
    if any(
        not isinstance(proposal, EquationTranscriptionProposal)
        for proposal in result.proposals
    ):
        raise TypeError("proposals contain an unsupported value")
    if any(
        not isinstance(warning, EquationTranscriptionWarning)
        for warning in result.warnings
    ):
        raise TypeError("warnings contain an unsupported value")
    if result.failure is not None and not isinstance(
        result.failure, EquationTranscriptionFailure
    ):
        raise TypeError("failure has an unsupported value")
    warning_ids = tuple(warning.warning_id for warning in result.warnings)
    if len(set(warning_ids)) != len(warning_ids):
        raise ValueError("warning IDs must be unique")
    formats = tuple(proposal.output_format for proposal in result.proposals)
    if len(set(formats)) != len(formats):
        raise ValueError("proposal formats must be unique")
    if result.status is EquationTranscriptionStatus.COMPLETED:
        if not result.proposals or result.failure is not None:
            raise ValueError(
                "completed result requires proposals and no failure"
            )
        if any(
            proposal.confidence is None
            or proposal.symbol_confidence_coverage
            is not EquationSymbolConfidenceCoverage.COMPLETE
            for proposal in result.proposals
        ):
            raise ValueError(
                "completed result requires assessed complete symbol confidence"
            )
    elif result.status is EquationTranscriptionStatus.PARTIAL:
        if not result.proposals or result.failure is None:
            raise ValueError(
                "partial result requires proposals and failure evidence"
            )
    elif result.status is EquationTranscriptionStatus.FAILED:
        if result.proposals or result.failure is None:
            raise ValueError(
                "failed result requires no proposals and a failure"
            )
    else:
        raise TypeError("transcription selection status is unsupported")
    if (
        result.status is not EquationTranscriptionStatus.COMPLETED
        and not result.warnings
    ):
        raise ValueError("partial or failed results require warning evidence")
    warning_id_set = set(warning_ids)
    warning_by_id = {warning.warning_id: warning for warning in result.warnings}
    for warning in result.warnings:
        if warning.selection_id != result.selection_id:
            raise ValueError("warning selection does not match result")
    for proposal in result.proposals:
        if (
            proposal.selection_id != result.selection_id
            or proposal.candidate_id != result.candidate_id
            or proposal.rendered_region_id != result.rendered_region_id
        ):
            raise ValueError("proposal source evidence does not match result")
        if not set(proposal.warning_ids).issubset(warning_id_set):
            raise ValueError("proposal references unknown warnings")
        if any(
            warning_by_id[warning_id].output_format
            not in (None, proposal.output_format)
            for warning_id in proposal.warning_ids
        ):
            raise ValueError("proposal references a warning for another format")
        if proposal.configuration_digest != result.configuration_digest:
            raise ValueError("proposal configuration does not match result")
        _same_output_identity(result, proposal)
    if result.failure is not None:
        if result.failure.selection_id != result.selection_id:
            raise ValueError("failure selection does not match result")
        if not set(result.failure.warning_ids).issubset(warning_id_set):
            raise ValueError("failure references unknown warnings")
    _validate_processor_identity(processor_identity, None)


def _validate_selection_result(
    result: EquationTranscriptionSelectionResult,
    selection: EquationTranscriptionSelection,
    configuration: EquationTranscriptionConfiguration,
) -> None:
    if result.selection_id != selection.selection_id:
        raise ValueError("selection result does not match selection")
    if result.candidate_id != selection.candidate.candidate_id:
        raise ValueError("selection result does not match candidate")
    if result.rendered_region_id != selection.rendered_region.region_id:
        raise ValueError("selection result does not match source image")
    if result.configuration_digest != configuration.configuration_digest:
        raise ValueError("selection result configuration is inconsistent")
    if len(result.proposals) > configuration.max_proposals_per_selection:
        raise EquationTranscriptionLimitError(
            "proposal count exceeds max_proposals_per_selection"
        )
    if len(result.warnings) > configuration.max_warnings_per_selection:
        raise EquationTranscriptionLimitError(
            "warning count exceeds max_warnings_per_selection"
        )
    requested = configuration.formats
    actual = tuple(proposal.output_format for proposal in result.proposals)
    expected_order = tuple(item for item in requested if item in set(actual))
    if actual != expected_order:
        raise ValueError("proposals are not in requested format order")
    if (
        result.status is EquationTranscriptionStatus.COMPLETED
        and actual != requested
    ):
        raise ValueError("completed result requires every requested format")
    identity = _identity_from_output(result)
    _validate_selection_result_intrinsic(result, identity)
    for proposal in result.proposals:
        if (
            len(proposal.text)
            > configuration.max_output_characters_per_proposal
        ):
            raise EquationTranscriptionLimitError(
                "proposal text exceeds its configured limit"
            )
        _validate_symbol_ranges(
            proposal.text,
            proposal.output_format,
            proposal.symbols,
            proposal.symbol_confidence_coverage,
            proposal.warning_ids,
            configuration.max_symbols_per_proposal,
        )
        for symbol in proposal.symbols:
            if len(symbol.text) > configuration.max_symbol_text_characters:
                raise EquationTranscriptionLimitError(
                    "symbol text exceeds its configured limit"
                )
            expected_status = _symbol_status(symbol.confidence, configuration)
            if symbol.status is not expected_status:
                raise ValueError(
                    "symbol status contradicts configured confidence threshold"
                )
    for warning in result.warnings:
        if len(warning.message) > configuration.max_warning_message_characters:
            raise EquationTranscriptionLimitError(
                "warning message exceeds its configured limit"
            )
        if len(warning.evidence) > configuration.max_warning_evidence_entries:
            raise EquationTranscriptionLimitError(
                "warning evidence exceeds its configured entry limit"
            )
        if sum(len(key) + len(value) for key, value in warning.evidence) > (
            configuration.max_warning_evidence_characters
        ):
            raise EquationTranscriptionLimitError(
                "warning evidence exceeds its configured character limit"
            )
        if (
            warning.output_format is not None
            and warning.output_format not in configuration.formats
        ):
            raise ValueError("warning format was not requested")
    if result.failure is not None and len(result.failure.message) > (
        configuration.max_failure_message_characters
    ):
        raise EquationTranscriptionLimitError(
            "failure message exceeds its configured limit"
        )
    expected_id = _selection_result_id(
        selection,
        result.status,
        result.proposals,
        result.warnings,
        result.failure,
        result.configuration_digest,
        identity,
        processor_identity_digest=result.processor_identity_digest,
    )
    if result.selection_result_id != expected_id:
        raise ValueError("selection-result ID does not match request evidence")


def _preflight_result(
    request: EquationTranscriptionRequest,
    selection_results: tuple[EquationTranscriptionSelectionResult, ...],
    processor_identity: EquationTranscriptionProcessorIdentity,
) -> None:
    if not isinstance(request, EquationTranscriptionRequest):
        raise TypeError("request must be an EquationTranscriptionRequest")
    _require_tuple("selection_results", selection_results)
    if len(selection_results) != len(request.selections):
        raise ValueError("every selection must have exactly one result")
    if any(
        not isinstance(item, EquationTranscriptionSelectionResult)
        for item in selection_results
    ):
        raise TypeError("selection_results contain an unsupported value")
    _validate_processor_identity(processor_identity, request.configuration)
    total_output = sum(
        len(proposal.text)
        for item in selection_results
        for proposal in item.proposals
    )
    total_symbols = sum(
        len(proposal.symbols)
        for item in selection_results
        for proposal in item.proposals
    )
    total_warnings = sum(len(item.warnings) for item in selection_results)
    configuration = request.configuration
    if total_output > configuration.max_total_output_characters:
        raise EquationTranscriptionLimitError(
            "output text exceeds max_total_output_characters"
        )
    if total_symbols > configuration.max_total_symbols:
        raise EquationTranscriptionLimitError(
            "symbols exceed max_total_symbols"
        )
    if total_warnings > configuration.max_total_warnings:
        raise EquationTranscriptionLimitError(
            "warnings exceed max_total_warnings"
        )
    for item in selection_results:
        _same_output_identity_from_processor(item, processor_identity)


def _overall_status(
    selection_results: tuple[EquationTranscriptionSelectionResult, ...],
) -> EquationTranscriptionStatus:
    statuses = tuple(item.status for item in selection_results)
    if all(
        status is EquationTranscriptionStatus.COMPLETED for status in statuses
    ):
        return EquationTranscriptionStatus.COMPLETED
    if all(status is EquationTranscriptionStatus.FAILED for status in statuses):
        return EquationTranscriptionStatus.FAILED
    return EquationTranscriptionStatus.PARTIAL


def _symbol_status(
    confidence: EquationTranscriptionConfidence | None,
    configuration: EquationTranscriptionConfiguration,
) -> EquationSymbolStatus:
    if confidence is None:
        return EquationSymbolStatus.UNASSESSED
    if confidence.value < configuration.low_confidence_threshold:
        return EquationSymbolStatus.LOW_CONFIDENCE
    return EquationSymbolStatus.PROPOSED


def _validate_processor_identity(
    processor_identity: EquationTranscriptionProcessorIdentity,
    configuration: EquationTranscriptionConfiguration | None,
) -> None:
    if not isinstance(
        processor_identity, EquationTranscriptionProcessorIdentity
    ):
        raise TypeError(
            "processor identity must be an "
            "EquationTranscriptionProcessorIdentity"
        )
    if configuration is not None:
        if len(processor_identity.resources) > configuration.max_resources:
            raise EquationTranscriptionLimitError(
                "resource identities exceed max_resources"
            )
        for value in (
            processor_identity.processor_name,
            processor_identity.processor_version,
            processor_identity.backend_name,
            processor_identity.backend_version,
            *(
                resource.resource_name
                for resource in processor_identity.resources
            ),
            *(
                resource.resource_identity
                for resource in processor_identity.resources
            ),
        ):
            if len(value) > configuration.max_identity_characters:
                raise EquationTranscriptionLimitError(
                    "processor identity exceeds max_identity_characters"
                )


def _output_processor_parts(
    processor_identity: EquationTranscriptionProcessorIdentity,
) -> tuple[str, str, str, str]:
    return (
        processor_identity.processor_name,
        processor_identity.processor_version,
        processor_identity.backend_name,
        processor_identity.backend_version,
    )


def _identity_from_output(
    output: EquationTranscriptionSymbol
    | EquationTranscriptionProposal
    | EquationTranscriptionSelectionResult,
) -> EquationTranscriptionProcessorIdentity:
    return EquationTranscriptionProcessorIdentity(
        processor_name=output.processor_name,
        processor_version=output.processor_version,
        backend_name=output.backend_name,
        backend_version=output.backend_version,
    )


def _same_output_identity(
    left: EquationTranscriptionProposal | EquationTranscriptionSelectionResult,
    right: EquationTranscriptionSymbol | EquationTranscriptionProposal,
) -> None:
    if (
        left.processor_identity_digest,
        left.processor_name,
        left.processor_version,
        left.backend_name,
        left.backend_version,
    ) != (
        right.processor_identity_digest,
        right.processor_name,
        right.processor_version,
        right.backend_name,
        right.backend_version,
    ):
        raise ValueError("transcription processor identity is inconsistent")


def _same_output_identity_from_processor(
    output: EquationTranscriptionSymbol
    | EquationTranscriptionProposal
    | EquationTranscriptionSelectionResult,
    processor_identity: EquationTranscriptionProcessorIdentity,
) -> None:
    if (
        output.processor_identity_digest,
        output.processor_name,
        output.processor_version,
        output.backend_name,
        output.backend_version,
    ) != (
        processor_identity.identity_digest,
        processor_identity.processor_name,
        processor_identity.processor_version,
        processor_identity.backend_name,
        processor_identity.backend_version,
    ):
        raise ValueError("output processor identity is inconsistent")


def _validate_confidence(
    confidence: EquationTranscriptionConfidence | None,
) -> None:
    if confidence is not None and not isinstance(
        confidence, EquationTranscriptionConfidence
    ):
        raise TypeError("confidence has an unsupported value")


def _validate_metadata(value: Metadata) -> None:
    _require_tuple("warning evidence", value)
    if len(value) > _MAX_WARNING_EVIDENCE_ENTRIES:
        raise EquationTranscriptionLimitError("warning evidence is too large")
    total_characters = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("warning evidence must contain immutable pairs")
        key, item = entry
        _bounded_string("warning evidence key", key, nonempty=True)
        _bounded_string("warning evidence value", item)
        total_characters += len(key) + len(item)
        if total_characters > _MAX_WARNING_EVIDENCE_CHARACTERS:
            raise EquationTranscriptionLimitError(
                "warning evidence exceeds its aggregate character limit"
            )


def _validate_contract_size(value: object, limit: int) -> None:
    _validate_walk_size(
        value,
        limit,
        skip_rendered_content=True,
        error_message="transcription result exceeds max_result_bytes",
    )


def _validate_identity_size(value: object, limit: int) -> None:
    _validate_walk_size(
        value,
        limit,
        skip_rendered_content=False,
        error_message="transcription identity exceeds its aggregate limit",
    )


def _validate_walk_size(
    value: object,
    limit: int,
    *,
    skip_rendered_content: bool,
    error_message: str,
) -> None:
    total = 0
    stack = [value]
    seen: set[int] = set()
    while stack:
        item = stack.pop()
        if item is None or isinstance(item, (bool, int, float, Enum)):
            total += 16
        elif isinstance(item, str):
            total += len(item.encode("utf-8")) + 8
        elif isinstance(item, bytes):
            total += len(item)
        elif isinstance(item, tuple):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            total += 8 * len(item)
            stack.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            for field in fields(item):
                total += len(field.name) + 3
                if (
                    skip_rendered_content
                    and isinstance(item, RenderedRegion)
                    and field.name == "content"
                ):
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError(
                "transcription contract contains unsupported evidence"
            )
        if total > limit:
            raise EquationTranscriptionLimitError(error_message)


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")


def _require_unique_strings(
    name: str,
    values: tuple[str, ...],
    *,
    required: bool = False,
) -> None:
    _require_tuple(name, values)
    if required and not values:
        raise ValueError(f"{name} must be non-empty")
    if len(values) > _MAX_TOTAL_WARNINGS:
        raise EquationTranscriptionLimitError(f"{name} are too numerous")
    for value in values:
        _bounded_string(name, value, nonempty=True)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _bounded_string(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
    limit: int = _MAX_IDENTITY_CHARACTERS,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must be non-empty")
    if len(value) > limit:
        raise EquationTranscriptionLimitError(f"{name} exceeds its limit")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonnegative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _unit_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be finite and within [0, 1]")
    return result


def _validate_sha256(name: str, value: str) -> None:
    if len(value) != 64:
        raise ValueError(f"{name} must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"{name} must be a SHA-256 hex digest") from error
