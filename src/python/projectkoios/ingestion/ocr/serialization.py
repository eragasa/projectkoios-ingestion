"""Strict reconstruction of immutable OCR evidence from JSON values."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, cast

from projectkoios.ingestion.models import BoundingBox, WarningSeverity
from projectkoios.ingestion.ocr.confidence import OCRConfidence
from projectkoios.ingestion.ocr.configuration import OCRConfiguration
from projectkoios.ingestion.ocr.failure import OCRFailure
from projectkoios.ingestion.ocr.identity.processor import OCRProcessorIdentity
from projectkoios.ingestion.ocr.identity.resource.language import (
    OCRLanguageResourceIdentity,
)
from projectkoios.ingestion.ocr.image.page import OCRPageImage
from projectkoios.ingestion.ocr.kind.failure import OCRFailureKind
from projectkoios.ingestion.ocr.kind.resource.identity import (
    OCRResourceIdentityKind,
)
from projectkoios.ingestion.ocr.line import OCRLine
from projectkoios.ingestion.ocr.mode.output import OCROutputMode
from projectkoios.ingestion.ocr.reference.native.text.block import (
    OCRNativeTextBlockReference,
)
from projectkoios.ingestion.ocr.request import OCRRequest
from projectkoios.ingestion.ocr.result.ocr import OCRResult
from projectkoios.ingestion.ocr.result.selection import OCRSelectionResult
from projectkoios.ingestion.ocr.selection import OCRSelection
from projectkoios.ingestion.ocr.status.result import OCRResultStatus
from projectkoios.ingestion.ocr.status.selection import OCRSelectionStatus
from projectkoios.ingestion.ocr.token import OCRToken
from projectkoios.ingestion.ocr.warning import OCRWarning
from projectkoios.ingestion.pdf.models import RegionColorMode, RenderedRegion


def deserialize_ocr_result(value: object) -> OCRResult:
    """Reconstruct and intrinsically validate one canonical OCR result value."""
    root = _object(
        value, {field.name for field in fields(OCRResult)}, "OCR result"
    )
    request = _request(root["request"])
    processor_identity = _processor_identity(root["processor_identity"])
    return OCRResult(
        result_id=_string(root["result_id"], "OCR result ID"),
        request=request,
        selection_results=tuple(
            _selection_result(item)
            for item in _array(root["selection_results"], "selection results")
        ),
        status=OCRResultStatus(_string(root["status"], "OCR result status")),
        cache_key=_string(root["cache_key"], "OCR cache key"),
        processor_identity=processor_identity,
        contract_version=_string(
            root["contract_version"], "OCR contract version"
        ),
    )


def _request(value: object) -> OCRRequest:
    data = _object(
        value, {field.name for field in fields(OCRRequest)}, "OCR request"
    )
    return OCRRequest(
        request_id=_string(data["request_id"], "OCR request ID"),
        selections=tuple(
            _selection(item)
            for item in _array(data["selections"], "OCR selections")
        ),
        configuration=_configuration(data["configuration"]),
        contract_version=_string(
            data["contract_version"], "OCR contract version"
        ),
    )


def _configuration(value: object) -> OCRConfiguration:
    names = {field.name for field in fields(OCRConfiguration)}
    data = _object(value, names, "OCR configuration")
    arguments = dict(data)
    arguments["languages"] = tuple(
        _array(arguments["languages"], "OCR languages")
    )
    arguments["output_mode"] = OCROutputMode(
        _string(arguments["output_mode"], "OCR output mode")
    )
    return OCRConfiguration(**cast(Any, arguments))


def _selection(value: object) -> OCRSelection:
    data = _object(
        value, {field.name for field in fields(OCRSelection)}, "OCR selection"
    )
    return OCRSelection(
        selection_id=_string(data["selection_id"], "OCR selection ID"),
        image=_image(data["image"]),
        native_text_blocks=tuple(
            _native_reference(item)
            for item in _array(
                data["native_text_blocks"], "native text references"
            )
        ),
        contract_version=_string(
            data["contract_version"], "OCR contract version"
        ),
    )


def _image(value: object) -> OCRPageImage:
    data = _object(
        value, {field.name for field in fields(OCRPageImage)}, "OCR image"
    )
    return OCRPageImage(
        image_id=_string(data["image_id"], "OCR image ID"),
        rendered_region=_region(data["rendered_region"]),
        contract_version=_string(
            data["contract_version"], "OCR contract version"
        ),
    )


def _region(value: object) -> RenderedRegion:
    data = _object(
        value,
        {field.name for field in fields(RenderedRegion)},
        "rendered region",
    )
    content = _object(data["content"], {"hex"}, "rendered region content")
    arguments = dict(data)
    arguments["content"] = bytes.fromhex(
        _string(content["hex"], "rendered region content")
    )
    arguments["source_bounding_box"] = _box(
        data["source_bounding_box"], "source bounding box"
    )
    arguments["effective_source_bounding_box"] = _box(
        data["effective_source_bounding_box"], "effective source bounding box"
    )
    arguments["pixel_to_source_matrix"] = tuple(
        _number(item, "pixel-to-source matrix")
        for item in _array(
            data["pixel_to_source_matrix"], "pixel-to-source matrix"
        )
    )
    arguments["color_mode"] = RegionColorMode(
        _string(data["color_mode"], "rendered region color mode")
    )
    return RenderedRegion(**cast(Any, arguments))


def _native_reference(value: object) -> OCRNativeTextBlockReference:
    data = _object(
        value,
        {field.name for field in fields(OCRNativeTextBlockReference)},
        "native text reference",
    )
    return OCRNativeTextBlockReference(**cast(Any, data))


def _processor_identity(value: object) -> OCRProcessorIdentity:
    data = _object(
        value,
        {field.name for field in fields(OCRProcessorIdentity)},
        "OCR processor identity",
    )
    return OCRProcessorIdentity(
        processor_name=_string(data["processor_name"], "processor name"),
        processor_version=_string(
            data["processor_version"], "processor version"
        ),
        backend_name=_string(data["backend_name"], "backend name"),
        backend_version=_string(data["backend_version"], "backend version"),
        language_resources=tuple(
            _language_resource(item)
            for item in _array(data["language_resources"], "language resources")
        ),
    )


def _language_resource(value: object) -> OCRLanguageResourceIdentity:
    data = _object(
        value,
        {field.name for field in fields(OCRLanguageResourceIdentity)},
        "OCR language resource",
    )
    return OCRLanguageResourceIdentity(
        language=_string(data["language"], "language"),
        resource_name=_string(data["resource_name"], "resource name"),
        identity_kind=OCRResourceIdentityKind(
            _string(data["identity_kind"], "resource identity kind")
        ),
        resource_identity=_string(
            data["resource_identity"], "resource identity"
        ),
    )


def _selection_result(value: object) -> OCRSelectionResult:
    data = _object(
        value,
        {field.name for field in fields(OCRSelectionResult)},
        "OCR selection result",
    )
    failure = data["failure"]
    return OCRSelectionResult(
        selection_result_id=_string(
            data["selection_result_id"], "selection result ID"
        ),
        selection_id=_string(data["selection_id"], "selection ID"),
        image_id=_string(data["image_id"], "image ID"),
        status=OCRSelectionStatus(_string(data["status"], "selection status")),
        tokens=tuple(
            _token(item) for item in _array(data["tokens"], "OCR tokens")
        ),
        lines=tuple(_line(item) for item in _array(data["lines"], "OCR lines")),
        warnings=tuple(
            _warning(item) for item in _array(data["warnings"], "OCR warnings")
        ),
        failure=None if failure is None else _failure(failure),
        configuration_digest=_string(
            data["configuration_digest"], "configuration digest"
        ),
        processor_name=_string(data["processor_name"], "processor name"),
        processor_version=_string(
            data["processor_version"], "processor version"
        ),
        backend_name=_string(data["backend_name"], "backend name"),
        backend_version=_string(data["backend_version"], "backend version"),
        contract_version=_string(
            data["contract_version"], "OCR contract version"
        ),
    )


def _token(value: object) -> OCRToken:
    data = _text_output(value, OCRToken, "OCR token")
    return OCRToken(**cast(Any, data))


def _line(value: object) -> OCRLine:
    data = _text_output(value, OCRLine, "OCR line")
    data["token_ids"] = tuple(_array(data["token_ids"], "OCR line token IDs"))
    return OCRLine(**cast(Any, data))


def _text_output(
    value: object, kind: type[OCRToken] | type[OCRLine], label: str
) -> dict[str, object]:
    data = dict(_object(value, {field.name for field in fields(kind)}, label))
    data["pixel_bounding_box"] = _box(
        data["pixel_bounding_box"], f"{label} pixel box"
    )
    data["source_bounding_box"] = _box(
        data["source_bounding_box"], f"{label} source box"
    )
    data["confidence"] = (
        None if data["confidence"] is None else _confidence(data["confidence"])
    )
    data["warning_ids"] = tuple(
        _array(data["warning_ids"], f"{label} warning IDs")
    )
    return data


def _confidence(value: object) -> OCRConfidence:
    data = _object(
        value, {field.name for field in fields(OCRConfidence)}, "OCR confidence"
    )
    return OCRConfidence(**cast(Any, data))


def _warning(value: object) -> OCRWarning:
    data = _object(
        value, {field.name for field in fields(OCRWarning)}, "OCR warning"
    )
    return OCRWarning(
        warning_id=_string(data["warning_id"], "warning ID"),
        selection_id=_string(data["selection_id"], "selection ID"),
        code=_string(data["code"], "warning code"),
        severity=WarningSeverity(_string(data["severity"], "warning severity")),
        message=_string(data["message"], "warning message"),
        evidence=_metadata(data["evidence"]),
    )


def _failure(value: object) -> OCRFailure:
    data = _object(
        value, {field.name for field in fields(OCRFailure)}, "OCR failure"
    )
    return OCRFailure(
        failure_id=_string(data["failure_id"], "failure ID"),
        selection_id=_string(data["selection_id"], "selection ID"),
        kind=OCRFailureKind(_string(data["kind"], "failure kind")),
        message=_string(data["message"], "failure message"),
        retryable=_boolean(data["retryable"], "failure retryable"),
        warning_ids=_strings(data["warning_ids"], "failure warning IDs"),
    )


def _object(value: object, expected: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f"{label} has an invalid shape")
    return value


def _array(value: object, label: str) -> list[object]:
    if type(value) is not list:
        raise TypeError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must be a string")
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{label} must be a boolean")
    return value


def _strings(value: object, label: str) -> tuple[str, ...]:
    return tuple(_string(item, label) for item in _array(value, label))


def _metadata(value: object) -> tuple[tuple[str, str], ...]:
    entries: list[tuple[str, str]] = []
    for item in _array(value, "warning evidence"):
        pair = _array(item, "warning evidence item")
        if len(pair) != 2:
            raise ValueError("warning evidence items must contain two strings")
        entries.append(
            (
                _string(pair[0], "warning evidence key"),
                _string(pair[1], "warning evidence value"),
            )
        )
    return tuple(entries)


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{label} must contain numbers")
    return float(value)


def _box(value: object, label: str) -> BoundingBox:
    values = _array(value, label)
    if len(values) != 4:
        raise ValueError(f"{label} must contain four coordinates")
    return tuple(_number(item, label) for item in values)  # type: ignore[return-value]
