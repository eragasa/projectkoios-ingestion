from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum, StrEnum
from itertools import islice

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    ExtractedPage,
    Metadata,
    WarningSeverity,
)
from projectkoios.ingestion.pdf.models import (
    PYMUPDF_COORDINATE_SYSTEM,
    RenderedRegion,
)

OCR_CONTRACT_VERSION = "1.0"
PIXEL_COORDINATE_SYSTEM = "image_pixels_top_left"

_MAX_SELECTIONS = 256
_MAX_IMAGES = 256
_MAX_PIXELS_PER_IMAGE = 25_000_000
_MAX_BYTES_PER_IMAGE = 100_000_000
_MAX_TOTAL_PIXELS = 25_000_000
_MAX_TOTAL_IMAGE_BYTES = 100_000_000
_MAX_LANGUAGES = 16
_MAX_LANGUAGE_CHARACTERS = 64
_MAX_NATIVE_PAGE_BLOCKS = 1_024
_MAX_NATIVE_PAGE_SOURCE_SPANS = 2_048
_MAX_NATIVE_TEXT_REFERENCES = 1_024
_MAX_IDENTITY_FIELD_CHARACTERS = 4_096
_MAX_TOTAL_IDENTITY_CHARACTERS = 1_000_000
_MAX_TOKENS_PER_SELECTION = 100_000
_MAX_LINES_PER_SELECTION = 25_000
_MAX_TEXT_CHARACTERS_PER_ITEM = 1_000_000
_MAX_TEXT_CHARACTERS_PER_SELECTION = 5_000_000
_MAX_WARNINGS_PER_SELECTION = 1_024
_MAX_WARNING_MESSAGE_CHARACTERS = 65_536
_MAX_WARNING_EVIDENCE_ENTRIES = 256
_MAX_WARNING_EVIDENCE_CHARACTERS = 1_000_000
_MAX_TOTAL_TOKENS = 100_000
_MAX_TOTAL_LINES = 25_000
_MAX_TOTAL_TEXT_CHARACTERS = 5_000_000
_MAX_TOTAL_WARNINGS = 4_096
_MAX_RESULT_BYTES = 64_000_000
_GRANDFATHERED_LANGUAGE_TAGS = frozenset(
    {
        "art-lojban",
        "cel-gaulish",
        "en-gb-oed",
        "i-ami",
        "i-bnn",
        "i-default",
        "i-enochian",
        "i-hak",
        "i-klingon",
        "i-lux",
        "i-mingo",
        "i-navajo",
        "i-pwn",
        "i-tao",
        "i-tay",
        "i-tsu",
        "no-bok",
        "no-nyn",
        "sgn-be-fr",
        "sgn-be-nl",
        "sgn-ch-de",
        "zh-guoyu",
        "zh-hakka",
        "zh-min",
        "zh-min-nan",
        "zh-xiang",
    }
)


class OCRContractLimitError(ValueError):
    """Raised when an OCR request or result exceeds configured bounds."""


class OCROutputMode(StrEnum):
    """The independently retained OCR evidence requested from an adapter."""

    TOKENS = "tokens"
    LINES = "lines"
    TOKENS_AND_LINES = "tokens_and_lines"


class OCRFailureKind(StrEnum):
    """Engine-neutral categories for a selection that did not complete."""

    INPUT_REJECTED = "input_rejected"
    RESOURCE_LIMIT = "resource_limit"
    PROCESSOR_UNAVAILABLE = "processor_unavailable"
    PROCESSOR_ERROR = "processor_error"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    OUTPUT_INVALID = "output_invalid"


class OCRSelectionStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class OCRResultStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class OCRConfidence:
    """An optional adapter score with explicit method and scale semantics."""

    value: float
    method: str
    method_version: str
    scale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _confidence_value(self.value))
        for name, value in (
            ("method", self.method),
            ("method_version", self.method_version),
            ("scale", self.scale),
        ):
            _hard_bounded_string(name, value, nonempty=True)

    def identity_parts(self) -> tuple[object, ...]:
        return (self.value, self.method, self.method_version, self.scale)


class OCRResourceIdentityKind(StrEnum):
    SHA256 = "sha256"
    EXPLICIT = "explicit"


@dataclass(frozen=True)
class OCRLanguageResourceIdentity:
    """One semantic language's selected backend resource identity."""

    language: str
    resource_name: str
    identity_kind: OCRResourceIdentityKind
    resource_identity: str

    def __post_init__(self) -> None:
        canonical_language = _canonical_language_tag(self.language)
        object.__setattr__(self, "language", canonical_language)
        _hard_bounded_string(
            "language resource name", self.resource_name, nonempty=True
        )
        if not isinstance(self.identity_kind, OCRResourceIdentityKind):
            raise ValueError("language resource identity kind is unsupported")
        _hard_bounded_string(
            "language resource identity",
            self.resource_identity,
            nonempty=True,
        )
        if self.identity_kind is OCRResourceIdentityKind.SHA256:
            _validate_sha256(
                "language resource identity", self.resource_identity
            )

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.language,
            self.resource_name,
            self.identity_kind.value,
            self.resource_identity,
        )


@dataclass(frozen=True)
class OCRProcessorIdentity:
    """Request-specific processor/backend and language-resource identity."""

    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    language_resources: tuple[OCRLanguageResourceIdentity, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("processor_name", self.processor_name),
            ("processor_version", self.processor_version),
            ("backend_name", self.backend_name),
            ("backend_version", self.backend_version),
        ):
            _hard_bounded_string(name, value, nonempty=True)
        _require_tuple("language_resources", self.language_resources)
        if len(self.language_resources) > _MAX_LANGUAGES:
            raise OCRContractLimitError("too many language resource bindings")
        for binding in self.language_resources:
            if not isinstance(binding, OCRLanguageResourceIdentity):
                raise TypeError(
                    "language_resources must contain resource identities"
                )
        languages = tuple(item.language for item in self.language_resources)
        if len(set(languages)) != len(languages):
            raise ValueError("language resource bindings must be unique")

    def validate_for(self, request: OCRRequest) -> None:
        languages = tuple(item.language for item in self.language_resources)
        if languages != request.configuration.languages:
            raise ValueError(
                "language resources must bind requested languages in order"
            )

    @property
    def identity_digest(self) -> str:
        return stable_id("ocr-processor-identity", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
            tuple(item.identity_parts() for item in self.language_resources),
        )


@dataclass(frozen=True)
class OCRConfiguration:
    """Language/output choices and deterministic OCR resource limits."""

    languages: tuple[str, ...] = ("und",)
    output_mode: OCROutputMode = OCROutputMode.TOKENS_AND_LINES
    max_selections: int = _MAX_SELECTIONS
    max_images: int = _MAX_IMAGES
    max_pixels_per_image: int = _MAX_PIXELS_PER_IMAGE
    max_bytes_per_image: int = _MAX_BYTES_PER_IMAGE
    max_total_pixels: int = _MAX_TOTAL_PIXELS
    max_total_image_bytes: int = _MAX_TOTAL_IMAGE_BYTES
    max_languages: int = _MAX_LANGUAGES
    max_language_characters: int = _MAX_LANGUAGE_CHARACTERS
    max_identity_field_characters: int = _MAX_IDENTITY_FIELD_CHARACTERS
    max_total_identity_characters: int = _MAX_TOTAL_IDENTITY_CHARACTERS
    max_tokens_per_selection: int = _MAX_TOKENS_PER_SELECTION
    max_lines_per_selection: int = _MAX_LINES_PER_SELECTION
    max_text_characters_per_item: int = _MAX_TEXT_CHARACTERS_PER_ITEM
    max_text_characters_per_selection: int = (
        _MAX_TEXT_CHARACTERS_PER_SELECTION
    )
    max_warnings_per_selection: int = _MAX_WARNINGS_PER_SELECTION
    max_warning_message_characters: int = (
        _MAX_WARNING_MESSAGE_CHARACTERS
    )
    max_warning_evidence_entries: int = _MAX_WARNING_EVIDENCE_ENTRIES
    max_total_tokens: int = _MAX_TOTAL_TOKENS
    max_total_lines: int = _MAX_TOTAL_LINES
    max_total_text_characters: int = _MAX_TOTAL_TEXT_CHARACTERS
    max_total_warnings: int = _MAX_TOTAL_WARNINGS
    max_result_bytes: int = _MAX_RESULT_BYTES

    def __post_init__(self) -> None:
        _require_tuple("languages", self.languages)
        integer_fields = (
            ("max_selections", _MAX_SELECTIONS),
            ("max_images", _MAX_IMAGES),
            ("max_pixels_per_image", _MAX_PIXELS_PER_IMAGE),
            ("max_bytes_per_image", _MAX_BYTES_PER_IMAGE),
            ("max_total_pixels", _MAX_TOTAL_PIXELS),
            ("max_total_image_bytes", _MAX_TOTAL_IMAGE_BYTES),
            ("max_languages", _MAX_LANGUAGES),
            ("max_language_characters", _MAX_LANGUAGE_CHARACTERS),
            (
                "max_identity_field_characters",
                _MAX_IDENTITY_FIELD_CHARACTERS,
            ),
            (
                "max_total_identity_characters",
                _MAX_TOTAL_IDENTITY_CHARACTERS,
            ),
            ("max_tokens_per_selection", _MAX_TOKENS_PER_SELECTION),
            ("max_lines_per_selection", _MAX_LINES_PER_SELECTION),
            (
                "max_text_characters_per_item",
                _MAX_TEXT_CHARACTERS_PER_ITEM,
            ),
            (
                "max_text_characters_per_selection",
                _MAX_TEXT_CHARACTERS_PER_SELECTION,
            ),
            ("max_warnings_per_selection", _MAX_WARNINGS_PER_SELECTION),
            (
                "max_warning_message_characters",
                _MAX_WARNING_MESSAGE_CHARACTERS,
            ),
            (
                "max_warning_evidence_entries",
                _MAX_WARNING_EVIDENCE_ENTRIES,
            ),
            ("max_total_tokens", _MAX_TOTAL_TOKENS),
            ("max_total_lines", _MAX_TOTAL_LINES),
            (
                "max_total_text_characters",
                _MAX_TOTAL_TEXT_CHARACTERS,
            ),
            ("max_total_warnings", _MAX_TOTAL_WARNINGS),
            ("max_result_bytes", _MAX_RESULT_BYTES),
        )
        for name, hard_maximum in integer_fields:
            value = getattr(self, name)
            _positive_integer(name, value)
            if value > hard_maximum:
                raise OCRContractLimitError(
                    f"{name} exceeds the implementation maximum "
                    f"({hard_maximum})"
                )
        if len(self.languages) > self.max_languages:
            raise OCRContractLimitError("language count exceeds max_languages")
        if not self.languages:
            raise ValueError("languages must be non-empty and unique")
        normalized_languages = tuple(
            _canonical_language_tag(language) for language in self.languages
        )
        if any(
            len(language) > self.max_language_characters
            for language in normalized_languages
        ):
            raise OCRContractLimitError(
                "language exceeds its configured limit"
            )
        if len(set(normalized_languages)) != len(normalized_languages):
            raise ValueError(
                "languages must be unique after BCP 47 canonicalization"
            )
        object.__setattr__(self, "languages", normalized_languages)
        if not isinstance(self.output_mode, OCROutputMode):
            raise ValueError("output_mode must be an OCROutputMode")

    @property
    def configuration_digest(self) -> str:
        return stable_id("ocr-configuration", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, getattr(self, name).value)
            if name == "output_mode"
            else (name, getattr(self, name))
            for name in self.__dataclass_fields__
        )


@dataclass(frozen=True)
class OCRPageImage:
    """An OCR image that retains one exact validated RenderedRegion."""

    image_id: str
    rendered_region: RenderedRegion
    contract_version: str = OCR_CONTRACT_VERSION

    @classmethod
    def from_rendered_region(cls, region: RenderedRegion) -> OCRPageImage:
        return cls(
            image_id=_ocr_image_id(region),
            rendered_region=region,
        )

    def __post_init__(self) -> None:
        if self.contract_version != OCR_CONTRACT_VERSION:
            raise ValueError("unsupported OCR image contract version")
        if not isinstance(self.rendered_region, RenderedRegion):
            raise TypeError("rendered_region must be a RenderedRegion")
        if self.image_id != _ocr_image_id(self.rendered_region):
            raise ValueError("OCR image ID does not match rendered evidence")

    def identity_parts(self) -> tuple[object, ...]:
        return _image_identity_parts(self.rendered_region)


@dataclass(frozen=True)
class OCRNativeTextBlockReference:
    """A source/page-linked reference to verified native text evidence."""

    block_id: str
    source_id: str
    source_blob_id: str
    page_index: int

    def __post_init__(self) -> None:
        for name, value in (
            ("block_id", self.block_id),
            ("source_id", self.source_id),
            ("source_blob_id", self.source_blob_id),
        ):
            _hard_bounded_string(name, value, nonempty=True)
        _nonnegative_integer("page_index", self.page_index)

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.block_id,
            self.source_id,
            self.source_blob_id,
            self.page_index,
        )


@dataclass(frozen=True)
class OCRSelection:
    """One explicit OCR selection; native IDs are coexistence evidence only."""

    selection_id: str
    image: OCRPageImage
    native_text_blocks: tuple[OCRNativeTextBlockReference, ...] = ()
    contract_version: str = OCR_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        image: OCRPageImage,
        *,
        native_text_page: ExtractedPage | None = None,
        native_text_block_ids: tuple[str, ...] = (),
    ) -> OCRSelection:
        _require_tuple("native_text_block_ids", native_text_block_ids)
        if len(native_text_block_ids) > _MAX_NATIVE_TEXT_REFERENCES:
            raise OCRContractLimitError("too many native text block IDs")
        _require_unique_strings(
            "native_text_block_ids",
            native_text_block_ids,
            string_limit=_MAX_IDENTITY_FIELD_CHARACTERS,
        )
        if bool(native_text_block_ids) != (native_text_page is not None):
            raise ValueError(
                "native text block IDs require their containing extracted page"
            )
        references: tuple[OCRNativeTextBlockReference, ...] = ()
        if native_text_page is not None:
            references = _native_text_references(
                image, native_text_page, native_text_block_ids
            )
        return cls(
            selection_id=_ocr_selection_id(image, references),
            image=image,
            native_text_blocks=references,
        )

    def __post_init__(self) -> None:
        if self.contract_version != OCR_CONTRACT_VERSION:
            raise ValueError("unsupported OCR selection contract version")
        if not isinstance(self.image, OCRPageImage):
            raise TypeError("image must be an OCRPageImage")
        _require_tuple("native_text_blocks", self.native_text_blocks)
        if len(self.native_text_blocks) > _MAX_NATIVE_TEXT_REFERENCES:
            raise OCRContractLimitError("too many native text references")
        if any(
            not isinstance(reference, OCRNativeTextBlockReference)
            for reference in self.native_text_blocks
        ):
            raise TypeError(
                "native_text_blocks must contain source-backed references"
            )
        reference_characters = sum(
            len(value)
            for reference in self.native_text_blocks
            for value in (
                reference.block_id,
                reference.source_id,
                reference.source_blob_id,
            )
        )
        if reference_characters > _MAX_TOTAL_IDENTITY_CHARACTERS:
            raise OCRContractLimitError(
                "native text references exceed the identity safety limit"
            )
        block_ids = tuple(item.block_id for item in self.native_text_blocks)
        if len(set(block_ids)) != len(block_ids):
            raise ValueError("native text block IDs must be unique")
        region = self.image.rendered_region
        for reference in self.native_text_blocks:
            if not isinstance(reference, OCRNativeTextBlockReference):
                raise TypeError(
                    "native_text_blocks must contain source-backed references"
                )
            if (
                reference.source_id != region.source_id
                or reference.source_blob_id != region.source_blob_id
                or reference.page_index != region.page_index
            ):
                raise ValueError(
                    "native text evidence must refer to the rendered "
                    "source page"
                )
        expected = _ocr_selection_id(self.image, self.native_text_blocks)
        if self.selection_id != expected:
            raise ValueError("OCR selection ID does not match its evidence")

    @property
    def native_text_block_ids(self) -> tuple[str, ...]:
        return tuple(item.block_id for item in self.native_text_blocks)

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.image.identity_parts(),
            tuple(item.identity_parts() for item in self.native_text_blocks),
        )


@dataclass(frozen=True)
class OCRRequest:
    """A non-empty, ordered, bounded OCR request."""

    request_id: str
    selections: tuple[OCRSelection, ...]
    configuration: OCRConfiguration
    contract_version: str = OCR_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        selections: Iterable[OCRSelection],
        *,
        configuration: OCRConfiguration | None = None,
    ) -> OCRRequest:
        config = configuration or OCRConfiguration()
        bounded = tuple(islice(selections, config.max_selections + 1))
        if len(bounded) > config.max_selections:
            raise OCRContractLimitError(
                "selection count exceeds max_selections"
            )
        _preflight_request(bounded, config)
        return cls(
            request_id=_ocr_request_id(bounded, config),
            selections=bounded,
            configuration=config,
        )

    def __post_init__(self) -> None:
        if self.contract_version != OCR_CONTRACT_VERSION:
            raise ValueError("unsupported OCR request contract version")
        _require_tuple("selections", self.selections)
        if not isinstance(self.configuration, OCRConfiguration):
            raise TypeError("configuration must be an OCRConfiguration")
        _preflight_request(self.selections, self.configuration)
        if self.request_id != _ocr_request_id(
            self.selections, self.configuration
        ):
            raise ValueError("OCR request ID does not match its evidence")


@dataclass(frozen=True)
class OCRWarning:
    """A stable selection-local warning reported by an OCR adapter."""

    warning_id: str
    selection_id: str
    code: str
    severity: WarningSeverity
    message: str
    evidence: Metadata = ()

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        code: str,
        severity: WarningSeverity,
        message: str,
        evidence: Metadata = (),
    ) -> OCRWarning:
        _hard_bounded_string("selection_id", selection_id, nonempty=True)
        _hard_bounded_string("warning code", code, nonempty=True)
        _hard_bounded_string(
            "warning message",
            message,
            nonempty=True,
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        if not isinstance(severity, WarningSeverity):
            raise ValueError("OCR warning severity is unsupported")
        _validate_metadata(evidence)
        return cls(
            warning_id=_ocr_warning_id(
                selection_id, code, severity, message, evidence
            ),
            selection_id=selection_id,
            code=code,
            severity=severity,
            message=message,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        _hard_bounded_string(
            "selection_id", self.selection_id, nonempty=True
        )
        _hard_bounded_string("warning code", self.code, nonempty=True)
        _hard_bounded_string(
            "warning message",
            self.message,
            nonempty=True,
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        if not isinstance(self.severity, WarningSeverity):
            raise ValueError("OCR warning severity is unsupported")
        _validate_metadata(self.evidence)
        expected = _ocr_warning_id(
            self.selection_id,
            self.code,
            self.severity,
            self.message,
            self.evidence,
        )
        if self.warning_id != expected:
            raise ValueError("OCR warning ID does not match its evidence")


@dataclass(frozen=True)
class OCRFailure:
    """Typed evidence explaining a partial or failed OCR selection."""

    failure_id: str
    selection_id: str
    kind: OCRFailureKind
    message: str
    retryable: bool
    warning_ids: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        kind: OCRFailureKind,
        message: str,
        retryable: bool,
        warning_ids: tuple[str, ...],
    ) -> OCRFailure:
        _hard_bounded_string("selection_id", selection_id, nonempty=True)
        if not isinstance(kind, OCRFailureKind):
            raise ValueError("OCR failure kind is unsupported")
        _hard_bounded_string(
            "failure message",
            message,
            nonempty=True,
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        if not isinstance(retryable, bool):
            raise ValueError("retryable must be a boolean")
        _require_unique_strings("warning_ids", warning_ids, required=True)
        return cls(
            failure_id=_ocr_failure_id(
                selection_id, kind, message, retryable, warning_ids
            ),
            selection_id=selection_id,
            kind=kind,
            message=message,
            retryable=retryable,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        _hard_bounded_string(
            "selection_id", self.selection_id, nonempty=True
        )
        if not isinstance(self.kind, OCRFailureKind):
            raise ValueError("OCR failure kind is unsupported")
        _hard_bounded_string(
            "failure message",
            self.message,
            nonempty=True,
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        if not isinstance(self.retryable, bool):
            raise ValueError("retryable must be a boolean")
        _require_unique_strings("warning_ids", self.warning_ids, required=True)
        expected = _ocr_failure_id(
            self.selection_id,
            self.kind,
            self.message,
            self.retryable,
            self.warning_ids,
        )
        if self.failure_id != expected:
            raise ValueError("OCR failure ID does not match its evidence")


@dataclass(frozen=True)
class OCRToken:
    """One ordered OCR token with image-pixel and mapped source geometry."""

    token_id: str
    selection_id: str
    image_id: str
    pixel_coordinate_system: str
    source_coordinate_system: str
    text: str
    pixel_bounding_box: BoundingBox
    source_bounding_box: BoundingBox
    confidence: OCRConfidence | None
    order: int
    line_order: int | None
    warning_ids: tuple[str, ...]
    configuration_digest: str
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str

    @classmethod
    def create(
        cls,
        *,
        selection: OCRSelection,
        configuration: OCRConfiguration,
        text: str,
        pixel_bounding_box: BoundingBox,
        confidence: OCRConfidence | None,
        order: int,
        line_order: int | None = None,
        warning_ids: tuple[str, ...] = (),
        processor_name: str,
        processor_version: str,
        backend_name: str,
        backend_version: str,
    ) -> OCRToken:
        _bounded_string(
            "token text",
            text,
            configuration.max_text_characters_per_item,
            nonempty=True,
        )
        pixel_box = _pixel_box(selection.image, pixel_bounding_box)
        source_box = _map_pixel_box(selection.image, pixel_box)
        _validate_confidence(confidence)
        _nonnegative_integer("order", order)
        _optional_nonnegative_integer("line_order", line_order)
        _require_unique_strings("warning_ids", warning_ids)
        _require_identity_fields(
            selection.selection_id,
            selection.image.image_id,
            configuration.configuration_digest,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        token_id = _ocr_token_id(
            selection.selection_id,
            selection.image.image_id,
            text,
            pixel_box,
            source_box,
            confidence,
            order,
            line_order,
            warning_ids,
            configuration.configuration_digest,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        return cls(
            token_id=token_id,
            selection_id=selection.selection_id,
            image_id=selection.image.image_id,
            pixel_coordinate_system=PIXEL_COORDINATE_SYSTEM,
            source_coordinate_system=(
                selection.image.rendered_region.coordinate_system
            ),
            text=text,
            pixel_bounding_box=pixel_box,
            source_bounding_box=source_box,
            confidence=confidence,
            order=order,
            line_order=line_order,
            warning_ids=warning_ids,
            configuration_digest=configuration.configuration_digest,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )

    def __post_init__(self) -> None:
        _validate_output_common(self)
        _optional_nonnegative_integer("line_order", self.line_order)
        expected = _ocr_token_id(
            self.selection_id,
            self.image_id,
            self.text,
            self.pixel_bounding_box,
            self.source_bounding_box,
            self.confidence,
            self.order,
            self.line_order,
            self.warning_ids,
            self.configuration_digest,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.token_id != expected:
            raise ValueError("OCR token ID does not match its evidence")


@dataclass(frozen=True)
class OCRLine:
    """One ordered OCR line, optionally retaining ordered token membership."""

    line_id: str
    selection_id: str
    image_id: str
    pixel_coordinate_system: str
    source_coordinate_system: str
    text: str
    pixel_bounding_box: BoundingBox
    source_bounding_box: BoundingBox
    confidence: OCRConfidence | None
    order: int
    token_ids: tuple[str, ...]
    warning_ids: tuple[str, ...]
    configuration_digest: str
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str

    @classmethod
    def create(
        cls,
        *,
        selection: OCRSelection,
        configuration: OCRConfiguration,
        text: str,
        pixel_bounding_box: BoundingBox,
        confidence: OCRConfidence | None,
        order: int,
        token_ids: tuple[str, ...] = (),
        warning_ids: tuple[str, ...] = (),
        processor_name: str,
        processor_version: str,
        backend_name: str,
        backend_version: str,
    ) -> OCRLine:
        _bounded_string(
            "line text",
            text,
            configuration.max_text_characters_per_item,
            nonempty=True,
        )
        pixel_box = _pixel_box(selection.image, pixel_bounding_box)
        source_box = _map_pixel_box(selection.image, pixel_box)
        _validate_confidence(confidence)
        _nonnegative_integer("order", order)
        _require_unique_strings("token_ids", token_ids)
        _require_unique_strings("warning_ids", warning_ids)
        _require_identity_fields(
            selection.selection_id,
            selection.image.image_id,
            configuration.configuration_digest,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        line_id = _ocr_line_id(
            selection.selection_id,
            selection.image.image_id,
            text,
            pixel_box,
            source_box,
            confidence,
            order,
            token_ids,
            warning_ids,
            configuration.configuration_digest,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        return cls(
            line_id=line_id,
            selection_id=selection.selection_id,
            image_id=selection.image.image_id,
            pixel_coordinate_system=PIXEL_COORDINATE_SYSTEM,
            source_coordinate_system=(
                selection.image.rendered_region.coordinate_system
            ),
            text=text,
            pixel_bounding_box=pixel_box,
            source_bounding_box=source_box,
            confidence=confidence,
            order=order,
            token_ids=token_ids,
            warning_ids=warning_ids,
            configuration_digest=configuration.configuration_digest,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )

    def __post_init__(self) -> None:
        _validate_output_common(self)
        _require_unique_strings("token_ids", self.token_ids)
        expected = _ocr_line_id(
            self.selection_id,
            self.image_id,
            self.text,
            self.pixel_bounding_box,
            self.source_bounding_box,
            self.confidence,
            self.order,
            self.token_ids,
            self.warning_ids,
            self.configuration_digest,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.line_id != expected:
            raise ValueError("OCR line ID does not match its evidence")


@dataclass(frozen=True)
class OCRSelectionResult:
    """Completed, partial, or failed evidence for exactly one selection."""

    selection_result_id: str
    selection_id: str
    image_id: str
    status: OCRSelectionStatus
    tokens: tuple[OCRToken, ...]
    lines: tuple[OCRLine, ...]
    warnings: tuple[OCRWarning, ...]
    failure: OCRFailure | None
    configuration_digest: str
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    contract_version: str = OCR_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection: OCRSelection,
        configuration: OCRConfiguration,
        status: OCRSelectionStatus,
        tokens: tuple[OCRToken, ...] = (),
        lines: tuple[OCRLine, ...] = (),
        warnings: tuple[OCRWarning, ...] = (),
        failure: OCRFailure | None = None,
        processor_name: str,
        processor_version: str,
        backend_name: str,
        backend_version: str,
    ) -> OCRSelectionResult:
        if not isinstance(status, OCRSelectionStatus):
            raise ValueError("OCR selection status is unsupported")
        _require_identity_fields(
            selection.selection_id,
            selection.image.image_id,
            configuration.configuration_digest,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        for name, values, limit in (
            ("tokens", tokens, configuration.max_tokens_per_selection),
            ("lines", lines, configuration.max_lines_per_selection),
            ("warnings", warnings, configuration.max_warnings_per_selection),
        ):
            _require_tuple(name, values)
            if len(values) > limit:
                raise OCRContractLimitError(
                    f"{name} exceed their configured per-selection limit"
                )
        result_id = _ocr_selection_result_id(
            selection.selection_id,
            selection.image.image_id,
            status,
            tokens,
            lines,
            warnings,
            failure,
            configuration.configuration_digest,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        result = cls(
            selection_result_id=result_id,
            selection_id=selection.selection_id,
            image_id=selection.image.image_id,
            status=status,
            tokens=tokens,
            lines=lines,
            warnings=warnings,
            failure=failure,
            configuration_digest=configuration.configuration_digest,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )
        _validate_selection_result(result, selection, configuration)
        return result

    def __post_init__(self) -> None:
        if self.contract_version != OCR_CONTRACT_VERSION:
            raise ValueError("unsupported OCR selection result version")
        for name in ("tokens", "lines", "warnings"):
            _require_tuple(name, getattr(self, name))
        if not isinstance(self.status, OCRSelectionStatus):
            raise ValueError("OCR selection status is unsupported")
        _require_identity_fields(
            self.selection_id,
            self.image_id,
            self.configuration_digest,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        _validate_selection_result_intrinsic(self)
        expected = _ocr_selection_result_id(
            self.selection_id,
            self.image_id,
            self.status,
            self.tokens,
            self.lines,
            self.warnings,
            self.failure,
            self.configuration_digest,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.selection_result_id != expected:
            raise ValueError(
                "OCR selection result ID does not match its evidence"
            )


@dataclass(frozen=True)
class OCRResult:
    """Ordered OCR outcomes retaining their complete bounded request."""

    result_id: str
    request: OCRRequest
    selection_results: tuple[OCRSelectionResult, ...]
    status: OCRResultStatus
    cache_key: str
    processor_identity: OCRProcessorIdentity
    contract_version: str = OCR_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: OCRRequest,
        selection_results: tuple[OCRSelectionResult, ...],
        processor_identity: OCRProcessorIdentity,
    ) -> OCRResult:
        if not isinstance(processor_identity, OCRProcessorIdentity):
            raise TypeError(
                "processor_identity must be an OCRProcessorIdentity"
            )
        processor_identity.validate_for(request)
        _require_tuple("selection_results", selection_results)
        _preflight_result_counts(request, selection_results)
        status = _overall_status(selection_results)
        cache_key = build_ocr_cache_key(
            request=request,
            processor_identity=processor_identity,
        )
        _validate_contract_size(
            (
                request,
                selection_results,
                status,
                cache_key,
                processor_identity,
            ),
            request.configuration.max_result_bytes,
        )
        result_id = _ocr_result_id(
            request,
            selection_results,
            status,
            cache_key,
            processor_identity.processor_name,
            processor_identity.processor_version,
            processor_identity.backend_name,
            processor_identity.backend_version,
        )
        return cls(
            result_id=result_id,
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
        if self.contract_version != OCR_CONTRACT_VERSION:
            raise ValueError("unsupported OCR result contract version")
        if not isinstance(self.request, OCRRequest):
            raise TypeError("request must be an OCRRequest")
        if not isinstance(self.processor_identity, OCRProcessorIdentity):
            raise TypeError(
                "processor_identity must be an OCRProcessorIdentity"
            )
        self.processor_identity.validate_for(self.request)
        _require_tuple("selection_results", self.selection_results)
        config = self.request.configuration
        if len(self.selection_results) != len(self.request.selections):
            raise ValueError("every OCR selection must have exactly one result")

        _preflight_result_counts(self.request, self.selection_results)
        total_text = sum(
            sum(len(token.text) for token in item.tokens)
            + sum(len(line.text) for line in item.lines)
            for item in self.selection_results
        )
        if total_text > config.max_total_text_characters:
            raise OCRContractLimitError(
                "text length exceeds max_total_text_characters"
            )

        for selection, selection_result in zip(
            self.request.selections, self.selection_results, strict=True
        ):
            _validate_selection_result(selection_result, selection, config)
            _same_processor_identity(self, selection_result)
        expected_status = _overall_status(self.selection_results)
        if self.status is not expected_status:
            raise ValueError(
                "overall OCR status contradicts selection statuses"
            )
        expected_cache_key = build_ocr_cache_key(
            request=self.request,
            processor_identity=self.processor_identity,
        )
        if self.cache_key != expected_cache_key:
            raise ValueError("OCR cache key does not match request evidence")
        _validate_contract_size(self, config.max_result_bytes)
        expected_id = _ocr_result_id(
            self.request,
            self.selection_results,
            self.status,
            self.cache_key,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.result_id != expected_id:
            raise ValueError("OCR result ID does not match its evidence")


def build_ocr_cache_key(
    *,
    request: OCRRequest,
    processor_identity: OCRProcessorIdentity,
    contract_version: str = OCR_CONTRACT_VERSION,
) -> str:
    """Build the complete derived-cache identity without storing a result."""
    _bounded_string(
        "OCR contract version",
        contract_version,
        request.configuration.max_identity_field_characters,
        nonempty=True,
    )
    if not isinstance(processor_identity, OCRProcessorIdentity):
        raise TypeError("processor_identity must be an OCRProcessorIdentity")
    processor_identity.validate_for(request)
    return stable_id(
        "ocr-cache",
        contract_version,
        tuple(selection.identity_parts() for selection in request.selections),
        request.configuration.identity_parts(),
        processor_identity.identity_parts(),
    )


def _native_text_references(
    image: OCRPageImage,
    page: ExtractedPage,
    block_ids: tuple[str, ...],
) -> tuple[OCRNativeTextBlockReference, ...]:
    if not isinstance(page, ExtractedPage):
        raise TypeError("native_text_page must be an ExtractedPage")
    region = image.rendered_region
    if page.page_index != region.page_index:
        raise ValueError("native text page does not match rendered page")
    _require_tuple("native text page blocks", page.blocks)
    if len(page.blocks) > _MAX_NATIVE_PAGE_BLOCKS:
        raise OCRContractLimitError(
            "native text page exceeds the block safety limit"
        )
    span_count = sum(len(block.source_spans) for block in page.blocks)
    if span_count > _MAX_NATIVE_PAGE_SOURCE_SPANS:
        raise OCRContractLimitError(
            "native text page exceeds the source-span safety limit"
        )
    blocks_by_id: dict[str, ExtractedBlock] = {}
    for block in page.blocks:
        _hard_bounded_string("native block ID", block.block_id, nonempty=True)
        if block.block_id in blocks_by_id:
            raise ValueError("native text page block IDs must be unique")
        blocks_by_id[block.block_id] = block
    references: list[OCRNativeTextBlockReference] = []
    for block_id in block_ids:
        referenced_block = blocks_by_id.get(block_id)
        if referenced_block is None:
            raise ValueError("native text block ID does not exist on the page")
        if referenced_block.kind != "text" or not isinstance(
            referenced_block.text, str
        ):
            raise ValueError(
                "native coexistence evidence must be text-bearing blocks"
            )
        if not referenced_block.source_spans:
            raise ValueError("native text block must retain source spans")
        if any(
            span.source_id != region.source_id
            or span.source_blob_id != region.source_blob_id
            or span.page_index != region.page_index
            for span in referenced_block.source_spans
        ):
            raise ValueError(
                "native text block must refer to the rendered source page"
            )
        references.append(
            OCRNativeTextBlockReference(
                block_id=referenced_block.block_id,
                source_id=region.source_id,
                source_blob_id=region.source_blob_id,
                page_index=region.page_index,
            )
        )
    return tuple(references)


def _preflight_request(
    selections: tuple[OCRSelection, ...], configuration: OCRConfiguration
) -> None:
    if not selections:
        raise ValueError("an OCR request requires at least one selection")
    if len(selections) > configuration.max_selections:
        raise OCRContractLimitError("selection count exceeds max_selections")
    if configuration.max_total_warnings < len(selections):
        raise OCRContractLimitError(
            "max_total_warnings must allow one failure warning per selection"
        )
    if any(not isinstance(item, OCRSelection) for item in selections):
        raise TypeError("request selections must be OCRSelection values")
    selection_ids = tuple(selection.selection_id for selection in selections)
    if len(set(selection_ids)) != len(selection_ids):
        raise ValueError("OCR selection IDs must be unique")
    image_by_id = {
        selection.image.image_id: selection.image for selection in selections
    }
    if len(image_by_id) > configuration.max_images:
        raise OCRContractLimitError("image count exceeds max_images")

    total_pixels = 0
    total_bytes = 0
    total_identity_characters = 0
    for selection in selections:
        region = selection.image.rendered_region
        identity_strings = (
            selection.selection_id,
            selection.image.image_id,
            region.region_id,
            region.source_id,
            region.source_blob_id,
            region.source_content_hash,
            region.content_sha256,
            region.coordinate_system,
            region.pixel_rounding,
            region.media_type,
            region.processor_name,
            region.processor_version,
            region.backend_name,
            region.backend_version,
            region.configuration_digest,
            *(
                (region.printed_page_label,)
                if region.printed_page_label is not None
                else ()
            ),
            *selection.native_text_block_ids,
        )
        for value in identity_strings:
            _bounded_string(
                "OCR identity field",
                value,
                configuration.max_identity_field_characters,
                nonempty=True,
            )
            total_identity_characters += len(value)
            if (
                total_identity_characters
                > configuration.max_total_identity_characters
            ):
                raise OCRContractLimitError(
                    "identity characters exceed max_total_identity_characters"
                )
    for image in image_by_id.values():
        region = image.rendered_region
        pixels = region.width_pixels * region.height_pixels
        if pixels > configuration.max_pixels_per_image:
            raise OCRContractLimitError(
                "image pixels exceed max_pixels_per_image"
            )
        if region.byte_length > configuration.max_bytes_per_image:
            raise OCRContractLimitError(
                "image bytes exceed max_bytes_per_image"
            )
        total_pixels += pixels
        total_bytes += region.byte_length
    if total_pixels > configuration.max_total_pixels:
        raise OCRContractLimitError("image pixels exceed max_total_pixels")
    if total_bytes > configuration.max_total_image_bytes:
        raise OCRContractLimitError("image bytes exceed max_total_image_bytes")


def _preflight_result_counts(
    request: OCRRequest,
    selection_results: tuple[OCRSelectionResult, ...],
) -> None:
    configuration = request.configuration
    if any(
        not isinstance(item, OCRSelectionResult) for item in selection_results
    ):
        raise TypeError(
            "selection_results must contain OCRSelectionResult values"
        )
    if len(selection_results) != len(request.selections):
        raise ValueError("every OCR selection must have exactly one result")
    total_tokens = sum(len(item.tokens) for item in selection_results)
    total_lines = sum(len(item.lines) for item in selection_results)
    total_warnings = sum(len(item.warnings) for item in selection_results)
    if total_tokens > configuration.max_total_tokens:
        raise OCRContractLimitError("token count exceeds max_total_tokens")
    if total_lines > configuration.max_total_lines:
        raise OCRContractLimitError("line count exceeds max_total_lines")
    if total_warnings > configuration.max_total_warnings:
        raise OCRContractLimitError("warning count exceeds max_total_warnings")


def _validate_selection_result_intrinsic(
    result: OCRSelectionResult,
) -> None:
    token_ids = tuple(item.token_id for item in result.tokens)
    line_ids = tuple(item.line_id for item in result.lines)
    warning_ids = tuple(item.warning_id for item in result.warnings)
    if len(set(token_ids)) != len(token_ids):
        raise ValueError("OCR token IDs must be unique")
    if len(set(line_ids)) != len(line_ids):
        raise ValueError("OCR line IDs must be unique")
    if len(set(warning_ids)) != len(warning_ids):
        raise ValueError("OCR warning IDs must be unique")
    if tuple(item.order for item in result.tokens) != tuple(
        range(len(result.tokens))
    ):
        raise ValueError("OCR token order must be contiguous and ordered")
    if tuple(item.order for item in result.lines) != tuple(
        range(len(result.lines))
    ):
        raise ValueError("OCR line order must be contiguous and ordered")
    for warning in result.warnings:
        if warning.selection_id != result.selection_id:
            raise ValueError("OCR warning refers to the wrong selection")
    outputs: tuple[OCRToken | OCRLine, ...] = (
        *result.tokens,
        *result.lines,
    )
    for output in outputs:
        if output.selection_id != result.selection_id:
            raise ValueError("OCR output refers to the wrong selection")
        if output.image_id != result.image_id:
            raise ValueError("OCR output refers to the wrong image")
        if output.configuration_digest != result.configuration_digest:
            raise ValueError("OCR output configuration is stale")
        _same_processor_identity(result, output)
        if not set(output.warning_ids).issubset(warning_ids):
            raise ValueError("OCR output warning links are unresolved")
    if result.status is OCRSelectionStatus.COMPLETED:
        if result.failure is not None:
            raise ValueError("completed OCR selection cannot have a failure")
    elif result.status is OCRSelectionStatus.PARTIAL:
        if result.failure is None or not result.warnings:
            raise ValueError(
                "partial OCR selection requires failure and warning evidence"
            )
        if not result.tokens and not result.lines:
            raise ValueError("partial OCR selection requires usable output")
    elif result.status is OCRSelectionStatus.FAILED:
        if result.tokens or result.lines:
            raise ValueError("failed OCR selection cannot contain output")
        if result.failure is None or not result.warnings:
            raise ValueError(
                "failed OCR selection requires failure and warning evidence"
            )
    if result.failure is not None:
        if result.failure.selection_id != result.selection_id:
            raise ValueError("OCR failure refers to the wrong selection")
        if not set(result.failure.warning_ids).issubset(warning_ids):
            raise ValueError("OCR failure warning links are unresolved")
    memberships = tuple(
        token_id for line in result.lines for token_id in line.token_ids
    )
    if memberships or (result.tokens and result.lines):
        if len(set(memberships)) != len(memberships):
            raise ValueError("OCR tokens must belong to at most one line")
        if set(memberships) != set(token_ids):
            raise ValueError("token and line membership must be complete")
        token_by_id = {token.token_id: token for token in result.tokens}
        for line in result.lines:
            for token_id in line.token_ids:
                token = token_by_id[token_id]
                if token.line_order != line.order:
                    raise ValueError("token line membership is contradictory")


def _validate_selection_result(
    result: OCRSelectionResult,
    selection: OCRSelection,
    configuration: OCRConfiguration,
) -> None:
    _validate_selection_result_intrinsic(result)
    if result.selection_id != selection.selection_id:
        raise ValueError("selection result refers to the wrong selection")
    if result.image_id != selection.image.image_id:
        raise ValueError("selection result refers to the wrong image")
    if result.configuration_digest != configuration.configuration_digest:
        raise ValueError("selection result configuration is stale")
    for value in (
        result.selection_id,
        result.image_id,
        result.configuration_digest,
        result.processor_name,
        result.processor_version,
        result.backend_name,
        result.backend_version,
    ):
        _bounded_string(
            "OCR identity field",
            value,
            configuration.max_identity_field_characters,
            nonempty=True,
        )
    if len(result.tokens) > configuration.max_tokens_per_selection:
        raise OCRContractLimitError(
            "token count exceeds max_tokens_per_selection"
        )
    if len(result.lines) > configuration.max_lines_per_selection:
        raise OCRContractLimitError(
            "line count exceeds max_lines_per_selection"
        )
    if len(result.warnings) > configuration.max_warnings_per_selection:
        raise OCRContractLimitError(
            "warning count exceeds max_warnings_per_selection"
        )
    if len({item.token_id for item in result.tokens}) != len(result.tokens):
        raise ValueError("OCR token IDs must be unique")
    if len({item.line_id for item in result.lines}) != len(result.lines):
        raise ValueError("OCR line IDs must be unique")
    warning_ids = tuple(warning.warning_id for warning in result.warnings)
    if len(set(warning_ids)) != len(warning_ids):
        raise ValueError("OCR warning IDs must be unique")
    if tuple(item.order for item in result.tokens) != tuple(
        range(len(result.tokens))
    ):
        raise ValueError("OCR token order must be contiguous and ordered")
    if tuple(item.order for item in result.lines) != tuple(
        range(len(result.lines))
    ):
        raise ValueError("OCR line order must be contiguous and ordered")

    text_characters = 0
    result_identity_strings = (
        result.selection_result_id,
        *(token.token_id for token in result.tokens),
        *(line.line_id for line in result.lines),
        *(warning.warning_id for warning in result.warnings),
    )
    for value in result_identity_strings:
        _bounded_string(
            "OCR result identity field",
            value,
            configuration.max_identity_field_characters,
            nonempty=True,
        )
    for warning in result.warnings:
        if warning.selection_id != selection.selection_id:
            raise ValueError("OCR warning refers to the wrong selection")
        _bounded_string(
            "warning code",
            warning.code,
            configuration.max_identity_field_characters,
            nonempty=True,
        )
        _bounded_string(
            "warning message",
            warning.message,
            configuration.max_warning_message_characters,
            nonempty=True,
        )
        if len(warning.evidence) > configuration.max_warning_evidence_entries:
            raise OCRContractLimitError(
                "warning evidence exceeds max_warning_evidence_entries"
            )
        for key, value in warning.evidence:
            _bounded_string(
                "warning evidence key",
                key,
                configuration.max_identity_field_characters,
                nonempty=True,
            )
            _bounded_string(
                "warning evidence value",
                value,
                configuration.max_warning_message_characters,
            )
    for token in result.tokens:
        _validate_output_against_selection(
            token, result, selection, configuration, warning_ids
        )
        text_characters += len(token.text)
    for line in result.lines:
        _validate_output_against_selection(
            line, result, selection, configuration, warning_ids
        )
        text_characters += len(line.text)
    if text_characters > configuration.max_text_characters_per_selection:
        raise OCRContractLimitError(
            "text length exceeds max_text_characters_per_selection"
        )

    mode = configuration.output_mode
    if result.status is OCRSelectionStatus.COMPLETED:
        if result.failure is not None:
            raise ValueError("completed OCR selection cannot have a failure")
        needs_tokens = mode in (
            OCROutputMode.TOKENS,
            OCROutputMode.TOKENS_AND_LINES,
        )
        needs_lines = mode in (
            OCROutputMode.LINES,
            OCROutputMode.TOKENS_AND_LINES,
        )
        has_output = bool(result.tokens or result.lines)
        if has_output and needs_tokens and not result.tokens:
            raise ValueError(
                "completed OCR selection is missing token evidence"
            )
        if has_output and needs_lines and not result.lines:
            raise ValueError("completed OCR selection is missing line evidence")
    elif result.status is OCRSelectionStatus.PARTIAL:
        if result.failure is None or not result.warnings:
            raise ValueError(
                "partial OCR selection requires failure and warning evidence"
            )
        if not result.tokens and not result.lines:
            raise ValueError("partial OCR selection requires usable output")
    else:
        if result.tokens or result.lines:
            raise ValueError("failed OCR selection cannot contain output")
        if result.failure is None or not result.warnings:
            raise ValueError(
                "failed OCR selection requires failure and warning evidence"
            )
    if result.failure is not None:
        if result.failure.selection_id != selection.selection_id:
            raise ValueError("OCR failure refers to the wrong selection")
        _bounded_string(
            "OCR failure ID",
            result.failure.failure_id,
            configuration.max_identity_field_characters,
            nonempty=True,
        )
        _bounded_string(
            "OCR failure message",
            result.failure.message,
            configuration.max_warning_message_characters,
            nonempty=True,
        )
        if not set(result.failure.warning_ids).issubset(warning_ids):
            raise ValueError("OCR failure warning links are unresolved")

    if mode is OCROutputMode.TOKENS:
        if result.lines:
            raise ValueError("token-only OCR result cannot contain lines")
        if any(token.line_order is not None for token in result.tokens):
            raise ValueError(
                "token-only OCR output cannot claim line membership"
            )
    elif mode is OCROutputMode.LINES:
        if result.tokens:
            raise ValueError("line-only OCR result cannot contain tokens")
        if any(line.token_ids for line in result.lines):
            raise ValueError("line-only OCR output cannot link absent tokens")
    elif result.tokens and result.lines:
        token_by_id = {token.token_id: token for token in result.tokens}
        memberships = tuple(
            token_id for line in result.lines for token_id in line.token_ids
        )
        if len(set(memberships)) != len(memberships):
            raise ValueError("OCR tokens must belong to at most one line")
        if set(memberships) != set(token_by_id):
            raise ValueError("token and line membership must be complete")
        for line in result.lines:
            for token_id in line.token_ids:
                token = token_by_id[token_id]
                if token.line_order != line.order:
                    raise ValueError("token line membership is contradictory")
                if not _box_contains(
                    line.pixel_bounding_box, token.pixel_bounding_box
                ):
                    raise ValueError("OCR line must contain its token boxes")


def _validate_output_against_selection(
    output: OCRToken | OCRLine,
    result: OCRSelectionResult,
    selection: OCRSelection,
    configuration: OCRConfiguration,
    warning_ids: tuple[str, ...],
) -> None:
    if output.selection_id != selection.selection_id:
        raise ValueError("OCR output refers to the wrong selection")
    if output.image_id != selection.image.image_id:
        raise ValueError("OCR output refers to the wrong image")
    if output.source_coordinate_system != (
        selection.image.rendered_region.coordinate_system
    ):
        raise ValueError("OCR output source coordinate system is stale")
    if output.configuration_digest != configuration.configuration_digest:
        raise ValueError("OCR output configuration is stale")
    _same_processor_identity(result, output)
    for value in (
        output.pixel_coordinate_system,
        output.source_coordinate_system,
        output.configuration_digest,
        output.processor_name,
        output.processor_version,
        output.backend_name,
        output.backend_version,
        *output.warning_ids,
    ):
        _bounded_string(
            "OCR output identity field",
            value,
            configuration.max_identity_field_characters,
            nonempty=True,
        )
    _bounded_string(
        "OCR output text",
        output.text,
        configuration.max_text_characters_per_item,
        nonempty=True,
    )
    if not set(output.warning_ids).issubset(warning_ids):
        raise ValueError("OCR output warning links are unresolved")
    expected_pixel = _pixel_box(selection.image, output.pixel_bounding_box)
    if output.pixel_bounding_box != expected_pixel:
        raise ValueError("OCR pixel box is not canonical")
    expected_source = _map_pixel_box(selection.image, expected_pixel)
    if output.source_bounding_box != expected_source:
        raise ValueError("OCR source box does not match pixel mapping")


def _validate_output_common(output: OCRToken | OCRLine) -> None:
    _require_identity_fields(
        output.selection_id,
        output.image_id,
        output.configuration_digest,
        output.processor_name,
        output.processor_version,
        output.backend_name,
        output.backend_version,
    )
    if output.pixel_coordinate_system != PIXEL_COORDINATE_SYSTEM:
        raise ValueError("OCR pixel coordinate system is unsupported")
    if output.source_coordinate_system != PYMUPDF_COORDINATE_SYSTEM:
        raise ValueError("OCR source coordinate system is unsupported")
    _hard_bounded_string(
        "OCR output text",
        output.text,
        nonempty=True,
        limit=_MAX_TEXT_CHARACTERS_PER_ITEM,
    )
    object.__setattr__(
        output,
        "pixel_bounding_box",
        _finite_box(output.pixel_bounding_box, "pixel_bounding_box"),
    )
    object.__setattr__(
        output,
        "source_bounding_box",
        _finite_box(output.source_bounding_box, "source_bounding_box"),
    )
    _validate_confidence(output.confidence)
    _nonnegative_integer("order", output.order)
    _require_unique_strings("warning_ids", output.warning_ids)


def _image_identity_parts(region: RenderedRegion) -> tuple[object, ...]:
    return (
        region.region_id,
        region.source_id,
        region.source_blob_id,
        region.source_content_hash,
        region.page_index,
        region.source_bounding_box,
        region.effective_source_bounding_box,
        region.pixel_to_source_matrix,
        region.pixel_rounding,
        region.page_rotation_degrees,
        region.selection_was_full_page,
        region.coordinate_system,
        region.resolution_dpi,
        region.color_mode.value,
        region.alpha,
        region.media_type,
        region.byte_length,
        region.width_pixels,
        region.height_pixels,
        region.content_sha256,
        region.processor_name,
        region.processor_version,
        region.backend_name,
        region.backend_version,
        region.configuration_digest,
    )


def _ocr_image_id(region: RenderedRegion) -> str:
    return stable_id(
        "ocr-image", OCR_CONTRACT_VERSION, _image_identity_parts(region)
    )


def _ocr_selection_id(
    image: OCRPageImage,
    native_text_blocks: tuple[OCRNativeTextBlockReference, ...],
) -> str:
    return stable_id(
        "ocr-selection",
        OCR_CONTRACT_VERSION,
        image.identity_parts(),
        tuple(item.identity_parts() for item in native_text_blocks),
    )


def _ocr_request_id(
    selections: tuple[OCRSelection, ...], configuration: OCRConfiguration
) -> str:
    return stable_id(
        "ocr-request",
        OCR_CONTRACT_VERSION,
        tuple(selection.identity_parts() for selection in selections),
        configuration.identity_parts(),
    )


def _ocr_warning_id(
    selection_id: str,
    code: str,
    severity: WarningSeverity,
    message: str,
    evidence: Metadata,
) -> str:
    return stable_id(
        "ocr-warning", selection_id, code, severity.value, message, evidence
    )


def _ocr_failure_id(
    selection_id: str,
    kind: OCRFailureKind,
    message: str,
    retryable: bool,
    warning_ids: tuple[str, ...],
) -> str:
    return stable_id(
        "ocr-failure",
        selection_id,
        kind.value,
        message,
        retryable,
        warning_ids,
    )


def _ocr_token_id(
    selection_id: str,
    image_id: str,
    text: str,
    pixel_box: BoundingBox,
    source_box: BoundingBox,
    confidence: OCRConfidence | None,
    order: int,
    line_order: int | None,
    warning_ids: tuple[str, ...],
    configuration_digest: str,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
) -> str:
    return stable_id(
        "ocr-token",
        selection_id,
        image_id,
        PIXEL_COORDINATE_SYSTEM,
        PYMUPDF_COORDINATE_SYSTEM,
        text,
        pixel_box,
        source_box,
        confidence,
        order,
        line_order,
        warning_ids,
        configuration_digest,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )


def _ocr_line_id(
    selection_id: str,
    image_id: str,
    text: str,
    pixel_box: BoundingBox,
    source_box: BoundingBox,
    confidence: OCRConfidence | None,
    order: int,
    token_ids: tuple[str, ...],
    warning_ids: tuple[str, ...],
    configuration_digest: str,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
) -> str:
    return stable_id(
        "ocr-line",
        selection_id,
        image_id,
        PIXEL_COORDINATE_SYSTEM,
        PYMUPDF_COORDINATE_SYSTEM,
        text,
        pixel_box,
        source_box,
        confidence,
        order,
        token_ids,
        warning_ids,
        configuration_digest,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )


def _ocr_selection_result_id(
    selection_id: str,
    image_id: str,
    status: OCRSelectionStatus,
    tokens: tuple[OCRToken, ...],
    lines: tuple[OCRLine, ...],
    warnings: tuple[OCRWarning, ...],
    failure: OCRFailure | None,
    configuration_digest: str,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
) -> str:
    return stable_id(
        "ocr-selection-result",
        OCR_CONTRACT_VERSION,
        selection_id,
        image_id,
        status.value,
        tuple(token.token_id for token in tokens),
        tuple(line.line_id for line in lines),
        tuple(warning.warning_id for warning in warnings),
        failure.failure_id if failure is not None else None,
        configuration_digest,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )


def _ocr_result_id(
    request: OCRRequest,
    selection_results: tuple[OCRSelectionResult, ...],
    status: OCRResultStatus,
    cache_key: str,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
) -> str:
    return stable_id(
        "ocr-result",
        OCR_CONTRACT_VERSION,
        request.request_id,
        tuple(item.selection_result_id for item in selection_results),
        status.value,
        cache_key,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )


def _overall_status(
    selection_results: tuple[OCRSelectionResult, ...],
) -> OCRResultStatus:
    if not selection_results:
        raise ValueError("OCR result requires selection results")
    if all(
        item.status is OCRSelectionStatus.COMPLETED
        for item in selection_results
    ):
        return OCRResultStatus.COMPLETED
    if all(
        item.status is OCRSelectionStatus.FAILED for item in selection_results
    ):
        return OCRResultStatus.FAILED
    return OCRResultStatus.PARTIAL


def _pixel_box(image: OCRPageImage, box: BoundingBox) -> BoundingBox:
    normalized = _finite_box(box, "pixel_bounding_box")
    x0, y0, x1, y1 = normalized
    region = image.rendered_region
    if x0 < 0.0 or y0 < 0.0:
        raise ValueError("OCR pixel box coordinates must be non-negative")
    if x1 > region.width_pixels or y1 > region.height_pixels:
        raise ValueError("OCR pixel box lies outside its image")
    return normalized


def _map_pixel_box(image: OCRPageImage, box: BoundingBox) -> BoundingBox:
    a, b, c, d, e, f = image.rendered_region.pixel_to_source_matrix
    x0, y0, x1, y1 = box
    corners = (
        (x0 * a + y0 * c + e, x0 * b + y0 * d + f),
        (x1 * a + y0 * c + e, x1 * b + y0 * d + f),
        (x0 * a + y1 * c + e, x0 * b + y1 * d + f),
        (x1 * a + y1 * c + e, x1 * b + y1 * d + f),
    )
    xs = tuple(point[0] for point in corners)
    ys = tuple(point[1] for point in corners)
    return _finite_box(
        (min(xs), min(ys), max(xs), max(ys)),
        "source_bounding_box",
    )


def _finite_box(box: BoundingBox, name: str) -> BoundingBox:
    if not isinstance(box, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    if len(box) != 4:
        raise ValueError(f"{name} must contain four coordinates")
    values: list[float] = []
    for coordinate in box:
        if isinstance(coordinate, bool) or not isinstance(
            coordinate, int | float
        ):
            raise ValueError(f"{name} coordinates must be finite numbers")
        try:
            value = float(coordinate)
        except OverflowError as error:
            raise ValueError(
                f"{name} coordinates must be finite numbers"
            ) from error
        if not math.isfinite(value):
            raise ValueError(f"{name} coordinates must be finite numbers")
        values.append(0.0 if value == 0.0 else value)
    x0, y0, x1, y1 = values
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"{name} must have positive area")
    return (x0, y0, x1, y1)


def _confidence_value(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("OCR confidence must be a finite number")
    try:
        normalized = float(value)
    except OverflowError as error:
        raise ValueError("OCR confidence must be a finite number") from error
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError("OCR confidence must be between zero and one")
    return 0.0 if normalized == 0.0 else normalized


def _validate_confidence(value: OCRConfidence | None) -> None:
    if value is not None and not isinstance(value, OCRConfidence):
        raise TypeError("confidence must be OCRConfidence or None")


def _box_contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def _same_processor_identity(first: object, second: object) -> None:
    identity_fields = (
        "processor_name",
        "processor_version",
        "backend_name",
        "backend_version",
    )
    if any(
        getattr(first, name) != getattr(second, name)
        for name in identity_fields
    ):
        raise ValueError("OCR processor/backend identity is contradictory")


def _validate_contract_size(value: object, limit: int) -> None:
    """Bound retained contract evidence without materializing canonical JSON."""
    total = 0
    stack: list[object] = [value]
    while stack:
        item = stack.pop()
        if item is None:
            increment = 4
        elif isinstance(item, str):
            increment = len(item.encode("utf-8")) + 2
        elif isinstance(item, bytes):
            increment = len(item)
        elif isinstance(item, Enum):
            stack.append(item.value)
            increment = 0
        elif isinstance(item, bool | int | float):
            increment = 32
        elif isinstance(item, tuple):
            increment = 2 + len(item)
            stack.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            increment = 2
            for field in fields(item):
                increment += len(field.name) + 3
                if (
                    isinstance(item, RenderedRegion)
                    and field.name == "content"
                ):
                    # Input PNG bytes have separate OCRConfiguration bounds.
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError(
                "OCR result contains unsupported contract evidence"
            )
        total += increment
        if total > limit:
            raise OCRContractLimitError(
                "OCR result exceeds max_result_bytes"
            )


def _canonical_language_tag(value: object) -> str:
    _hard_bounded_string(
        "language",
        value,
        nonempty=True,
        limit=_MAX_LANGUAGE_CHARACTERS,
    )
    assert isinstance(value, str)
    lowered = value.casefold()
    if lowered in _GRANDFATHERED_LANGUAGE_TAGS:
        return lowered
    if "_" in value or value.startswith("-") or value.endswith("-"):
        raise ValueError("language must be a well-formed BCP 47 tag")
    subtags = value.split("-")
    if any(
        not 1 <= len(subtag) <= 8
        or not subtag.isascii()
        or not subtag.isalnum()
        for subtag in subtags
    ):
        raise ValueError("language must be a well-formed BCP 47 tag")
    if subtags[0].casefold() == "x":
        if len(subtags) < 2:
            raise ValueError("language must be a well-formed BCP 47 tag")
        return "-".join(subtag.lower() for subtag in subtags)

    primary = subtags[0]
    if not primary.isalpha() or not 2 <= len(primary) <= 8:
        raise ValueError("language must be a well-formed BCP 47 tag")
    canonical = [primary.lower()]
    index = 1
    if len(primary) in (2, 3):
        extlang_count = 0
        while (
            index < len(subtags)
            and extlang_count < 3
            and len(subtags[index]) == 3
            and subtags[index].isalpha()
        ):
            canonical.append(subtags[index].lower())
            index += 1
            extlang_count += 1
    if (
        index < len(subtags)
        and len(subtags[index]) == 4
        and subtags[index].isalpha()
    ):
        canonical.append(subtags[index].title())
        index += 1
    if index < len(subtags) and (
        len(subtags[index]) == 2
        and subtags[index].isalpha()
        or len(subtags[index]) == 3
        and subtags[index].isdigit()
    ):
        canonical.append(subtags[index].upper())
        index += 1

    variants: set[str] = set()
    while index < len(subtags) and (
        5 <= len(subtags[index]) <= 8
        or len(subtags[index]) == 4
        and subtags[index][0].isdigit()
    ):
        variant = subtags[index].lower()
        if variant in variants:
            raise ValueError("language variants must be unique")
        variants.add(variant)
        canonical.append(variant)
        index += 1

    extensions: set[str] = set()
    while (
        index < len(subtags)
        and len(subtags[index]) == 1
        and subtags[index].casefold() != "x"
    ):
        singleton = subtags[index].lower()
        if singleton in extensions:
            raise ValueError("language extensions must be unique")
        extensions.add(singleton)
        canonical.append(singleton)
        index += 1
        start = index
        while index < len(subtags) and 2 <= len(subtags[index]) <= 8:
            canonical.append(subtags[index].lower())
            index += 1
        if index == start:
            raise ValueError("language extension has no value")

    if index < len(subtags) and subtags[index].casefold() == "x":
        canonical.append("x")
        index += 1
        if index == len(subtags):
            raise ValueError("language private use has no value")
        canonical.extend(subtag.lower() for subtag in subtags[index:])
        index = len(subtags)
    if index != len(subtags):
        raise ValueError("language must be a well-formed BCP 47 tag")
    return "-".join(canonical)


def _validate_sha256(name: str, value: object) -> None:
    _hard_bounded_string(name, value, nonempty=True, limit=64)
    assert isinstance(value, str)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _hard_bounded_string(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
    limit: int = _MAX_IDENTITY_FIELD_CHARACTERS,
) -> None:
    if not isinstance(value, str) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise ValueError(f"{name} must be a {qualifier}string")
    if len(value) > limit:
        raise OCRContractLimitError(
            f"{name} exceeds the implementation maximum ({limit})"
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _validate_metadata(metadata: Metadata) -> None:
    _require_tuple("evidence", metadata)
    if len(metadata) > _MAX_WARNING_EVIDENCE_ENTRIES:
        raise OCRContractLimitError(
            "warning evidence exceeds the implementation maximum"
        )
    total_characters = 0
    for entry in metadata:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("warning evidence entries must be immutable pairs")
        _hard_bounded_string(
            "warning evidence key", entry[0], nonempty=True
        )
        _hard_bounded_string(
            "warning evidence value",
            entry[1],
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        total_characters += len(entry[0]) + len(entry[1])
        if total_characters > _MAX_WARNING_EVIDENCE_CHARACTERS:
            raise OCRContractLimitError(
                "warning evidence exceeds the character safety limit"
            )
    if len({key for key, _ in metadata}) != len(metadata):
        raise ValueError("warning evidence keys must be unique")


def _require_identity_fields(*values: str) -> None:
    for value in values:
        _hard_bounded_string("OCR identity field", value, nonempty=True)


def _require_unique_strings(
    name: str,
    values: tuple[str, ...],
    *,
    required: bool = False,
    string_limit: int = _MAX_IDENTITY_FIELD_CHARACTERS,
) -> None:
    _require_tuple(name, values)
    if required and not values:
        raise ValueError(f"{name} must be non-empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")
    for value in values:
        _hard_bounded_string(
            name, value, nonempty=True, limit=string_limit
        )


def _bounded_string(
    name: str, value: str, limit: int, *, nonempty: bool = False
) -> None:
    if not isinstance(value, str) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise ValueError(f"{name} must be a {qualifier}string")
    if len(value) > limit:
        raise OCRContractLimitError(f"{name} exceeds its configured limit")
    _valid_utf8_string(name, value, nonempty=nonempty)


def _valid_utf8_string(
    name: str, value: object, *, nonempty: bool = False
) -> None:
    if not isinstance(value, str) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise ValueError(f"{name} must be a {qualifier}string")
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


def _optional_nonnegative_integer(name: str, value: object) -> None:
    if value is not None:
        _nonnegative_integer(name, value)


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
