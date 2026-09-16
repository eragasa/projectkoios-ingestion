from __future__ import annotations

import hashlib
import sys
import zlib
from dataclasses import FrozenInstanceError, replace
from typing import Protocol

import pytest
from projectkoios.ingestion import (
    OCR_CONTRACT_VERSION,
    PIXEL_COORDINATE_SYSTEM,
    ExtractedBlock,
    ExtractedPage,
    OCRConfidence,
    OCRConfiguration,
    OCRContractLimitError,
    OCRFailure,
    OCRFailureKind,
    OCRLanguageResourceIdentity,
    OCRLine,
    OCROutputMode,
    OCRPageImage,
    OCRProcessor,
    OCRProcessorIdentity,
    OCRRequest,
    OCRResourceIdentityKind,
    OCRResult,
    OCRResultStatus,
    OCRSelection,
    OCRSelectionResult,
    OCRSelectionStatus,
    OCRToken,
    OCRWarning,
    RegionRenderConfiguration,
    RenderedRegion,
    SourceDocument,
    SourceSpan,
    WarningSeverity,
    build_ocr_cache_key,
)

PROCESSOR = "synthetic-ocr-processor"
PROCESSOR_VERSION = "1"
BACKEND = "synthetic-backend"
BACKEND_VERSION = "2"
IDENTITY = {
    "processor_name": PROCESSOR,
    "processor_version": PROCESSOR_VERSION,
    "backend_name": BACKEND,
    "backend_version": BACKEND_VERSION,
}


def _png(width: int = 100, height: int = 50, suffix: bytes = b"") -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return (
            len(payload).to_bytes(4, "big")
            + kind
            + payload
            + crc.to_bytes(4, "big")
        )

    fill = sum(suffix) % 256
    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes((8, 2, 0, 0, 0))
    )
    row = b"\x00" + bytes((fill, 0, 0)) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def _image(
    *,
    source_id: str = "document:ocr",
    page_index: int = 0,
    native_rotation: int = 0,
    suffix: bytes = b"",
    source_suffix: bytes = b"",
) -> OCRPageImage:
    source = SourceDocument.from_bytes(
        b"synthetic-pdf-"
        + source_id.encode()
        + bytes((page_index,))
        + source_suffix,
        source_id=source_id,
        media_type="application/pdf",
        locator="memory://synthetic.pdf",
    )
    transforms = {
        0: (
            (1.0, 0.0, 0.0, 1.0, 10.0, 20.0),
            (10.0, 20.0, 110.0, 70.0),
        ),
        90: (
            (0.0, 1.0, -1.0, 0.0, 60.0, 10.0),
            (10.0, 10.0, 60.0, 110.0),
        ),
        180: (
            (-1.0, 0.0, 0.0, -1.0, 110.0, 70.0),
            (10.0, 20.0, 110.0, 70.0),
        ),
        270: (
            (0.0, -1.0, 1.0, 0.0, 10.0, 110.0),
            (10.0, 10.0, 60.0, 110.0),
        ),
    }
    matrix, effective = transforms[native_rotation]
    source_box = effective
    config = RegionRenderConfiguration(resolution_dpi=72)
    region = RenderedRegion.create(
        source=source,
        page_index=page_index,
        printed_page_label=str(page_index + 1),
        source_bounding_box=source_box,
        effective_source_bounding_box=effective,
        pixel_to_source_matrix=matrix,
        page_rotation_degrees=native_rotation,
        selection_was_full_page=False,
        configuration=config,
        content=_png(suffix=suffix),
        width_pixels=100,
        height_pixels=50,
        processor_name="synthetic-region-renderer",
        processor_version="1",
        backend_name="synthetic-pdf-backend",
        backend_version="1",
    )
    return OCRPageImage.from_rendered_region(region)


def _native_page(
    image: OCRPageImage, block_ids: tuple[str, ...]
) -> ExtractedPage:
    region = image.rendered_region
    blocks = tuple(
        ExtractedBlock(
            block_id=block_id,
            kind="text",
            source_spans=(
                SourceSpan(
                    source_id=region.source_id,
                    source_blob_id=region.source_blob_id,
                    page_index=region.page_index,
                    bounding_box=(1.0, 1.0, 2.0, 2.0),
                ),
            ),
            extraction_method="synthetic-native-text",
            confidence=1.0,
            text=f"Native {index}",
        )
        for index, block_id in enumerate(block_ids)
    )
    return ExtractedPage(
        page_index=region.page_index,
        width=120.0,
        height=120.0,
        blocks=blocks,
        coordinate_system=region.coordinate_system,
        rotation_degrees=region.page_rotation_degrees,
    )


def _request(
    *,
    mode: OCROutputMode = OCROutputMode.TOKENS_AND_LINES,
    images: tuple[OCRPageImage, ...] | None = None,
    native_ids: tuple[tuple[str, ...], ...] | None = None,
    **configuration_changes: object,
) -> OCRRequest:
    actual_images = images or (_image(),)
    ids = native_ids or tuple(() for _ in actual_images)
    configuration = OCRConfiguration(
        output_mode=mode,
        **configuration_changes,  # type: ignore[arg-type]
    )
    selections = tuple(
        OCRSelection.create(
            image,
            native_text_page=(
                _native_page(image, block_ids) if block_ids else None
            ),
            native_text_block_ids=block_ids,
        )
        for image, block_ids in zip(actual_images, ids, strict=True)
    )
    return OCRRequest.create(selections, configuration=configuration)


def _confidence(value: float) -> OCRConfidence:
    return OCRConfidence(
        value=value,
        method="synthetic-score",
        method_version="1",
        scale="unit_interval",
    )


def _processor_identity(
    languages: tuple[str, ...] = ("und",),
    *,
    resource_suffix: str = "v1",
    **changes: str,
) -> OCRProcessorIdentity:
    values = {**IDENTITY, **changes}
    return OCRProcessorIdentity(
        processor_name=values["processor_name"],
        processor_version=values["processor_version"],
        backend_name=values["backend_name"],
        backend_version=values["backend_version"],
        language_resources=tuple(
            OCRLanguageResourceIdentity(
                language=language,
                resource_name=f"synthetic-{language}",
                identity_kind=OCRResourceIdentityKind.EXPLICIT,
                resource_identity=f"{language}-{resource_suffix}",
            )
            for language in languages
        ),
    )


def _warning(
    selection: OCRSelection, code: str = "ocr.uncertain"
) -> OCRWarning:
    return OCRWarning.create(
        selection_id=selection.selection_id,
        code=code,
        severity=WarningSeverity.WARNING,
        message="Synthetic OCR warning",
        evidence=(("reason", "fixture"),),
    )


def _token(
    request: OCRRequest,
    *,
    selection_index: int = 0,
    order: int = 0,
    line_order: int | None = None,
    text: str = "Alpha",
    warning_ids: tuple[str, ...] = (),
) -> OCRToken:
    return OCRToken.create(
        selection=request.selections[selection_index],
        configuration=request.configuration,
        text=text,
        pixel_bounding_box=(10.0 + order * 20, 5.0, 25.0 + order * 20, 20.0),
        confidence=_confidence(0.81),
        order=order,
        line_order=line_order,
        warning_ids=warning_ids,
        **IDENTITY,
    )


def _line(
    request: OCRRequest,
    *,
    selection_index: int = 0,
    token_ids: tuple[str, ...] = (),
    text: str = "Alpha",
) -> OCRLine:
    return OCRLine.create(
        selection=request.selections[selection_index],
        configuration=request.configuration,
        text=text,
        pixel_bounding_box=(5.0, 2.0, 80.0, 25.0),
        confidence=_confidence(0.77),
        order=0,
        token_ids=token_ids,
        **IDENTITY,
    )


def _completed(
    request: OCRRequest, selection_index: int = 0
) -> OCRSelectionResult:
    mode = request.configuration.output_mode
    token = (
        _token(
            request,
            selection_index=selection_index,
            line_order=(0 if mode is OCROutputMode.TOKENS_AND_LINES else None),
        )
        if mode is not OCROutputMode.LINES
        else None
    )
    line = (
        _line(
            request,
            selection_index=selection_index,
            token_ids=(token.token_id,) if token is not None else (),
        )
        if mode is not OCROutputMode.TOKENS
        else None
    )
    return OCRSelectionResult.create(
        selection=request.selections[selection_index],
        configuration=request.configuration,
        status=OCRSelectionStatus.COMPLETED,
        tokens=(token,) if token is not None else (),
        lines=(line,) if line is not None else (),
        **IDENTITY,
    )


def _result(
    request: OCRRequest,
    selection_results: tuple[OCRSelectionResult, ...],
    *,
    resource_suffix: str = "v1",
    **identity_changes: str,
) -> OCRResult:
    return OCRResult.create(
        request=request,
        selection_results=selection_results,
        processor_identity=_processor_identity(
            request.configuration.languages,
            resource_suffix=resource_suffix,
            **identity_changes,
        ),
    )


def _failed(
    request: OCRRequest, selection_index: int = 0
) -> OCRSelectionResult:
    selection = request.selections[selection_index]
    warning = _warning(selection, "ocr.processor_error")
    failure = OCRFailure.create(
        selection_id=selection.selection_id,
        kind=OCRFailureKind.PROCESSOR_ERROR,
        message="Synthetic failure",
        retryable=True,
        warning_ids=(warning.warning_id,),
    )
    return OCRSelectionResult.create(
        selection=selection,
        configuration=request.configuration,
        status=OCRSelectionStatus.FAILED,
        warnings=(warning,),
        failure=failure,
        **IDENTITY,
    )


def test__ocr_contracts__represent_token_line_and_combined_output() -> None:
    for mode in (
        OCROutputMode.TOKENS,
        OCROutputMode.LINES,
        OCROutputMode.TOKENS_AND_LINES,
    ):
        request = _request(mode=mode)
        selection_result = _completed(request)
        result = _result(request, (selection_result,))

        assert result.status is OCRResultStatus.COMPLETED
        assert bool(selection_result.tokens) is (
            mode is not OCROutputMode.LINES
        )
        assert bool(selection_result.lines) is (
            mode is not OCROutputMode.TOKENS
        )
        assert result.request.selections[0].image.rendered_region.content
        assert result.cache_key == build_ocr_cache_key(
            request=request,
            processor_identity=_processor_identity(
                request.configuration.languages
            ),
        )


def test__ocr_contracts__represent_failed_partial_and_mixed_native_pages() -> (
    None
):
    first = _image(page_index=0)
    second = _image(page_index=1)
    request = _request(
        images=(first, second),
        native_ids=(("native:block:1", "native:block:2"), ()),
    )
    completed = _completed(request, 0)
    failed = _failed(request, 1)

    result = _result(request, (completed, failed))

    assert result.status is OCRResultStatus.PARTIAL
    assert result.selection_results[1].failure is not None
    assert not result.selection_results[1].tokens
    assert request.selections[0].native_text_block_ids == (
        "native:block:1",
        "native:block:2",
    )
    assert completed.tokens[0].text == "Alpha"


def test__ocr_contracts__represent_partial_selection_with_typed_evidence() -> (
    None
):
    request = _request()
    selection = request.selections[0]
    warning = _warning(selection, "ocr.output_truncated")
    token = _token(
        request,
        line_order=None,
        warning_ids=(warning.warning_id,),
    )
    failure = OCRFailure.create(
        selection_id=selection.selection_id,
        kind=OCRFailureKind.RESOURCE_LIMIT,
        message="Configured line limit reached",
        retryable=False,
        warning_ids=(warning.warning_id,),
    )
    partial = OCRSelectionResult.create(
        selection=selection,
        configuration=request.configuration,
        status=OCRSelectionStatus.PARTIAL,
        tokens=(token,),
        warnings=(warning,),
        failure=failure,
        **IDENTITY,
    )

    result = _result(request, (partial,))

    assert result.status is OCRResultStatus.PARTIAL
    assert partial.failure.kind is OCRFailureKind.RESOURCE_LIMIT


@pytest.mark.parametrize(
    ("rotation", "expected_source_box"),
    (
        (0, (20.0, 25.0, 40.0, 35.0)),
        (90, (45.0, 20.0, 55.0, 40.0)),
        (180, (80.0, 55.0, 100.0, 65.0)),
        (270, (15.0, 80.0, 25.0, 100.0)),
    ),
)
def test__ocr_coordinates__map_pixels_to_source_for_rotated_image(
    rotation: int, expected_source_box: tuple[float, float, float, float]
) -> None:
    request = _request(
        mode=OCROutputMode.TOKENS,
        images=(_image(native_rotation=rotation),),
    )
    token = OCRToken.create(
        selection=request.selections[0],
        configuration=request.configuration,
        text="rotated",
        pixel_bounding_box=(10.0, 5.0, 30.0, 15.0),
        confidence=_confidence(1.0),
        order=0,
        **IDENTITY,
    )

    assert PIXEL_COORDINATE_SYSTEM == "image_pixels_top_left"
    assert token.pixel_coordinate_system == PIXEL_COORDINATE_SYSTEM
    assert token.source_coordinate_system == (
        "pymupdf_unrotated_cropbox_points_top_left"
    )
    assert token.source_bounding_box == expected_source_box
    region = request.selections[0].image.rendered_region
    assert region.page_rotation_degrees == rotation

    a, b, c, d, e, f = region.pixel_to_source_matrix
    determinant = a * d - b * c
    source_corners = (
        (expected_source_box[0], expected_source_box[1]),
        (expected_source_box[2], expected_source_box[1]),
        (expected_source_box[0], expected_source_box[3]),
        (expected_source_box[2], expected_source_box[3]),
    )
    round_trip = tuple(
        (
            (d * (x - e) - c * (y - f)) / determinant,
            (-b * (x - e) + a * (y - f)) / determinant,
        )
        for x, y in source_corners
    )
    assert (
        min(x for x, _ in round_trip),
        min(y for _, y in round_trip),
        max(x for x, _ in round_trip),
        max(y for _, y in round_trip),
    ) == token.pixel_bounding_box
    with pytest.raises(ValueError, match="outside"):
        OCRToken.create(
            selection=request.selections[0],
            configuration=request.configuration,
            text="outside",
            pixel_bounding_box=(0.0, 0.0, 101.0, 1.0),
            confidence=_confidence(1.0),
            order=0,
            **IDENTITY,
        )


def test__ocr_request__preserves_order_and_bounds_infinite_iterables() -> None:
    first = OCRSelection.create(_image(page_index=0))
    second = OCRSelection.create(_image(page_index=1))
    request = OCRRequest.create((second, first))
    assert [
        item.image.rendered_region.page_index for item in request.selections
    ] == [
        1,
        0,
    ]

    consumed = 0

    def selections():
        nonlocal consumed
        while True:
            consumed += 1
            if consumed > 3:
                raise AssertionError("consumed beyond selection limit plus one")
            yield first

    with pytest.raises(OCRContractLimitError, match="max_selections"):
        OCRRequest.create(
            selections(),
            configuration=OCRConfiguration(max_selections=2),
        )
    assert consumed == 3


def test__ocr_cache_identity__is_stable_and_covers_every_dimension() -> None:
    base = _request(native_ids=(("native:1",),))
    identity = _processor_identity(base.configuration.languages)
    base_key = build_ocr_cache_key(
        request=base, processor_identity=identity
    )
    assert (
        build_ocr_cache_key(request=base, processor_identity=identity)
        == base_key
    )

    changed_requests = (
        _request(
            images=(_image(suffix=b"changed"),), native_ids=(("native:1",),)
        ),
        _request(
            images=(_image(source_suffix=b"changed"),),
            native_ids=(("native:1",),),
        ),
        _request(native_ids=(("native:2",),)),
        _request(
            mode=OCROutputMode.TOKENS,
            native_ids=(("native:1",),),
        ),
        _request(native_ids=(("native:1",),), max_total_tokens=99_999),
    )
    for changed in changed_requests:
        changed_identity = _processor_identity(
            changed.configuration.languages
        )
        assert build_ocr_cache_key(
            request=changed, processor_identity=changed_identity
        ) != base_key

    french = _request(native_ids=(("native:1",),), languages=("fr",))
    assert build_ocr_cache_key(
        request=french,
        processor_identity=_processor_identity(("fr",)),
    ) != base_key

    ordered = _request(
        images=(_image(page_index=0), _image(page_index=1)),
        native_ids=(("native:1",), ()),
    )
    reversed_order = OCRRequest.create(
        tuple(reversed(ordered.selections)),
        configuration=ordered.configuration,
    )
    ordered_identity = _processor_identity(ordered.configuration.languages)
    assert build_ocr_cache_key(
        request=ordered, processor_identity=ordered_identity
    ) != build_ocr_cache_key(
        request=reversed_order, processor_identity=ordered_identity
    )

    for field in (
        "processor_name",
        "processor_version",
        "backend_name",
        "backend_version",
    ):
        changed_identity = _processor_identity(**{field: "other"})
        assert build_ocr_cache_key(
            request=base, processor_identity=changed_identity
        ) != base_key
    assert build_ocr_cache_key(
        request=base,
        processor_identity=_processor_identity(resource_suffix="v2"),
    ) != base_key
    assert build_ocr_cache_key(
        request=base,
        processor_identity=identity,
        contract_version="future",
    ) != base_key


def test__ocr_contracts__reject_tampering_cross_links_and_mutation() -> None:
    request = _request()
    selection_result = _completed(request)
    result = _result(request, (selection_result,))

    with pytest.raises(FrozenInstanceError):
        request.request_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="token ID"):
        replace(selection_result.tokens[0], text="tampered")
    with pytest.raises(ValueError, match="token ID"):
        replace(
            selection_result.tokens[0],
            source_bounding_box=(0.0, 0.0, 1.0, 1.0),
            token_id=selection_result.tokens[0].token_id,
        )
    other_request = _request(images=(_image(page_index=1),))
    with pytest.raises(ValueError, match="wrong selection"):
        replace(
            selection_result,
            tokens=(_token(other_request, line_order=0),),
        )
    with pytest.raises(ValueError, match="status"):
        replace(result, selection_results=(_failed(request),))
    with pytest.raises(ValueError, match="cache key"):
        replace(
            result,
            processor_identity=_processor_identity(resource_suffix="v2"),
        )
    with pytest.raises(ValueError, match="image ID"):
        replace(request.selections[0].image, image_id="ocr-image:stale")


def test__ocr_contracts__reject_hostile_values_and_enforce_bounds() -> None:
    image = _image()
    with pytest.raises(TypeError, match="tuple"):
        OCRConfiguration(languages=["en"])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="positive integer"):
        OCRConfiguration(max_tokens_per_selection=True)  # type: ignore[arg-type]
    with pytest.raises(OCRContractLimitError, match="implementation maximum"):
        OCRConfiguration(max_selections=257)
    with pytest.raises(ValueError, match="UTF-8"):
        OCRConfiguration(languages=("\ud800",))
    duplicate_ids = ("native:1", "native:1")
    with pytest.raises(ValueError, match="unique"):
        OCRSelection.create(
            image,
            native_text_page=_native_page(image, duplicate_ids),
            native_text_block_ids=duplicate_ids,
        )
    with pytest.raises(OCRContractLimitError, match="image pixels"):
        _request(max_pixels_per_image=4_999)
    with pytest.raises(OCRContractLimitError, match="implementation maximum"):
        OCRWarning.create(
            selection_id="selection",
            code="ocr.hostile",
            severity=WarningSeverity.WARNING,
            message="x" * 65_537,
        )

    request = _request(
        mode=OCROutputMode.TOKENS,
        max_text_characters_per_item=4,
    )
    for confidence in (float("nan"), float("inf"), True, 10**400):
        with pytest.raises(ValueError, match="confidence"):
            OCRConfidence(
                value=confidence,  # type: ignore[arg-type]
                method="synthetic",
                method_version="1",
                scale="unit_interval",
            )
    with pytest.raises(OCRContractLimitError, match="configured limit"):
        _token(request, text="12345")
    with pytest.raises((ValueError, OverflowError), match="finite"):
        OCRToken.create(
            selection=request.selections[0],
            configuration=request.configuration,
            text="ok",
            pixel_bounding_box=(0.0, 0.0, float("inf"), 1.0),
            confidence=_confidence(1.0),
            order=0,
            **IDENTITY,
        )


def test__ocr_request__enforces_image_language_and_identity_bounds() -> None:
    images = (_image(page_index=0), _image(page_index=1))
    cases = (
        ({"max_images": 1}, "max_images"),
        ({"max_total_pixels": 9_999}, "max_total_pixels"),
        ({"max_bytes_per_image": 1}, "max_bytes_per_image"),
        ({"max_total_image_bytes": 1}, "max_total_image_bytes"),
        ({"max_identity_field_characters": 8}, "configured limit"),
        ({"max_total_identity_characters": 8}, "identity characters"),
    )
    for changes, message in cases:
        with pytest.raises(OCRContractLimitError, match=message):
            _request(images=images, **changes)

    with pytest.raises(OCRContractLimitError, match="max_languages"):
        OCRConfiguration(languages=("en", "fr"), max_languages=1)
    with pytest.raises(OCRContractLimitError, match="configured limit"):
        OCRConfiguration(
            languages=("en-Latn-US-variant1",),
            max_language_characters=4,
        )


def test__ocr_result__enforces_output_warning_and_aggregate_bounds() -> None:
    token_limited = _request(
        mode=OCROutputMode.TOKENS,
        max_tokens_per_selection=1,
    )
    with pytest.raises(OCRContractLimitError, match="per-selection"):
        OCRSelectionResult.create(
            selection=token_limited.selections[0],
            configuration=token_limited.configuration,
            status=OCRSelectionStatus.COMPLETED,
            tokens=(
                _token(token_limited, order=0),
                _token(token_limited, order=1),
            ),
            **IDENTITY,
        )

    warning_limited = _request(
        mode=OCROutputMode.TOKENS,
        max_warning_message_characters=4,
    )
    warning = _warning(warning_limited.selections[0])
    token = _token(warning_limited)
    with pytest.raises(OCRContractLimitError, match="warning message"):
        OCRSelectionResult.create(
            selection=warning_limited.selections[0],
            configuration=warning_limited.configuration,
            status=OCRSelectionStatus.COMPLETED,
            tokens=(token,),
            warnings=(warning,),
            **IDENTITY,
        )

    images = (_image(page_index=0), _image(page_index=1))
    aggregate = _request(
        mode=OCROutputMode.TOKENS,
        images=images,
        max_total_tokens=1,
    )
    completed = (_completed(aggregate, 0), _completed(aggregate, 1))
    with pytest.raises(OCRContractLimitError, match="max_total_tokens"):
        _result(aggregate, completed)

    size_limited = _request(
        mode=OCROutputMode.TOKENS,
        max_result_bytes=1,
    )
    with pytest.raises(OCRContractLimitError, match="max_result_bytes"):
        _result(size_limited, (_completed(size_limited),))


def test__ocr_contracts__allow_blank_success_and_optional_confidence() -> None:
    for mode in OCROutputMode:
        request = _request(mode=mode)
        blank = OCRSelectionResult.create(
            selection=request.selections[0],
            configuration=request.configuration,
            status=OCRSelectionStatus.COMPLETED,
            **IDENTITY,
        )
        result = _result(request, (blank,))
        assert result.status is OCRResultStatus.COMPLETED
        assert not blank.tokens
        assert not blank.lines

    token_request = _request(mode=OCROutputMode.TOKENS)
    token = OCRToken.create(
        selection=token_request.selections[0],
        configuration=token_request.configuration,
        text="No score",
        pixel_bounding_box=(0.0, 0.0, 10.0, 10.0),
        confidence=None,
        order=0,
        **IDENTITY,
    )
    assert token.confidence is None


def test__ocr_languages_and_resource_bindings_are_engine_neutral() -> None:
    configuration = OCRConfiguration(
        languages=("EN-us", "zh-hant-tw", "und")
    )
    assert configuration.languages == ("en-US", "zh-Hant-TW", "und")
    with pytest.raises(ValueError, match="unique"):
        OCRConfiguration(languages=("en-US", "EN-us"))
    with pytest.raises(ValueError, match="BCP 47"):
        OCRConfiguration(languages=("eng_US",))

    request = _request(languages=("en", "fr"))
    identity = _processor_identity(("en", "fr"))
    identity.validate_for(request)
    with pytest.raises(ValueError, match="requested languages"):
        _processor_identity(("fr", "en")).validate_for(request)
    with pytest.raises(ValueError, match="SHA-256"):
        OCRLanguageResourceIdentity(
            language="en",
            resource_name="synthetic-en",
            identity_kind=OCRResourceIdentityKind.SHA256,
            resource_identity="not-a-digest",
        )


def test__ocr_native_text_evidence_is_verified_against_source_page() -> None:
    image = _image(page_index=0)
    page = _native_page(image, ("native:1",))
    selection = OCRSelection.create(
        image,
        native_text_page=page,
        native_text_block_ids=("native:1",),
    )
    assert selection.native_text_block_ids == ("native:1",)

    with pytest.raises(ValueError, match="does not exist"):
        OCRSelection.create(
            image,
            native_text_page=page,
            native_text_block_ids=("missing",),
        )
    with pytest.raises(ValueError, match="rendered page"):
        OCRSelection.create(
            image,
            native_text_page=_native_page(
                _image(source_id="document:other", page_index=1),
                ("native:1",),
            ),
            native_text_block_ids=("native:1",),
        )
    with pytest.raises(ValueError, match="rendered source page"):
        OCRSelection.create(
            image,
            native_text_page=_native_page(
                _image(source_id="document:other", page_index=0),
                ("native:1",),
            ),
            native_text_block_ids=("native:1",),
        )


def test__ocr_page_images_require_immutable_complete_png_evidence() -> None:
    region = _image().rendered_region
    with pytest.raises(TypeError, match="immutable bytes"):
        replace(region, content=bytearray(region.content))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="positive integer"):
        replace(region, width_pixels=True)

    truncated = region.content[:-1]
    with pytest.raises(ValueError, match="PNG"):
        replace(
            region,
            content=truncated,
            byte_length=len(truncated),
            content_sha256=hashlib.sha256(truncated).hexdigest(),
        )


def test__ocr_protocol__is_public_and_imports_no_engine() -> None:
    assert OCR_CONTRACT_VERSION == "1.0"
    assert issubclass(OCRProcessor, Protocol)
    assert hasattr(OCRProcessor, "identity_for")
    assert not any(
        name.casefold().startswith(("tesseract", "pytesseract"))
        for name in sys.modules
    )
