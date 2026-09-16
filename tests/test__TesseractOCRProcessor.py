from __future__ import annotations

import hashlib
import os
import sys
import textwrap
import time
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Protocol

import pytest
from projectkoios.ingestion import (
    TESSERACT_ADAPTER_VERSION,
    ExtractedBlock,
    ExtractedPage,
    OCRConfiguration,
    OCRFailureKind,
    OCROutputMode,
    OCRPageImage,
    OCRProcessor,
    OCRRequest,
    OCRResourceIdentityKind,
    OCRResultStatus,
    OCRSelection,
    OCRSelectionStatus,
    RegionRenderConfiguration,
    RenderedRegion,
    SourceDocument,
    SourceSpan,
    TesseractAdapterConfiguration,
    TesseractAdapterConfigurationError,
    TesseractLanguageBinding,
    TesseractOCRProcessor,
    build_ocr_cache_key,
)

FIXTURE = Path("tests/fixtures/ocr/synthetic-text.png")
FIXTURE_SHA256 = (
    "1c5310c3ad5dd58229724f3f11a48fcba5e9dab3d870499f143e4a1df8296c7b"
)
TSV_HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\t"
    "top\twidth\theight\tconf\ttext"
)
TSV_WORDS = (
    TSV_HEADER
    + "\n5\t1\t1\t1\t1\t1\t2\t4\t25\t8\t96.0\tKOIOS"
    + "\n5\t1\t1\t1\t1\t2\t30\t4\t20\t8\t84.0\tOCR"
    + "\n"
)


def _request(
    *,
    pages: int = 1,
    output_mode: OCROutputMode = OCROutputMode.TOKENS_AND_LINES,
    languages: tuple[str, ...] = ("en",),
    native_text: bool = False,
    **configuration_changes: object,
) -> OCRRequest:
    content = FIXTURE.read_bytes()
    source = SourceDocument.from_bytes(
        b"%PDF-1.7\nsynthetic OCR fixture source\n",
        source_id="fixture:tesseract-adapter",
        media_type="application/pdf",
        locator="memory://tesseract-fixture.pdf",
    )
    render_configuration = RegionRenderConfiguration(resolution_dpi=72)
    selections = []
    for page_index in range(pages):
        region = RenderedRegion.create(
            source=source,
            page_index=page_index,
            printed_page_label=str(page_index + 1),
            source_bounding_box=(0.0, 0.0, 148.0, 22.0),
            effective_source_bounding_box=(0.0, 0.0, 148.0, 22.0),
            pixel_to_source_matrix=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            page_rotation_degrees=0,
            selection_was_full_page=True,
            configuration=render_configuration,
            content=content,
            width_pixels=148,
            height_pixels=22,
            processor_name="synthetic-region-renderer",
            processor_version="1",
            backend_name="synthetic-pdf-backend",
            backend_version="1",
        )
        image = OCRPageImage.from_rendered_region(region)
        if native_text:
            block_id = f"native:{page_index}"
            native_page = ExtractedPage(
                page_index=page_index,
                width=148.0,
                height=22.0,
                blocks=(
                    ExtractedBlock(
                        block_id=block_id,
                        kind="text",
                        source_spans=(
                            SourceSpan(
                                source_id=region.source_id,
                                source_blob_id=region.source_blob_id,
                                page_index=page_index,
                                bounding_box=(2.0, 4.0, 50.0, 12.0),
                            ),
                        ),
                        extraction_method="synthetic-native-text",
                        confidence=1.0,
                        text="Native evidence",
                    ),
                ),
                coordinate_system=region.coordinate_system,
                rotation_degrees=0,
            )
            selections.append(
                OCRSelection.create(
                    image,
                    native_text_page=native_page,
                    native_text_block_ids=(block_id,),
                )
            )
        else:
            selections.append(OCRSelection.create(image))
    configuration = OCRConfiguration(
        languages=languages,
        output_mode=output_mode,
        **configuration_changes,  # type: ignore[arg-type]
    )
    return OCRRequest.create(tuple(selections), configuration=configuration)


def _resource(tmp_path: Path, content: bytes = b"traineddata-v1") -> Path:
    path = tmp_path / "eng.traineddata"
    path.write_bytes(content)
    return path


def _fake_tesseract(
    tmp_path: Path,
    *,
    behavior: str = "success",
    version: str = "5.4.1",
) -> Path:
    path = tmp_path / f"fake-tesseract-{behavior}-{version.replace('.', '-')}"
    script = f"""\
#!{sys.executable}
import hashlib
import pathlib
import sys
import time

HEADER = {TSV_HEADER!r}
WORDS = {TSV_WORDS!r}
if sys.argv[1:] == ["--version"]:
    print("tesseract {version}")
    raise SystemExit(0)

input_path = pathlib.Path(sys.argv[1])
if hashlib.sha256(input_path.read_bytes()).hexdigest() != {FIXTURE_SHA256!r}:
    print("wrong input image", file=sys.stderr)
    raise SystemExit(8)
tessdata = pathlib.Path(sys.argv[sys.argv.index("--tessdata-dir") + 1])
if not (tessdata / "eng.traineddata").is_file():
    print("staged resource missing", file=sys.stderr)
    raise SystemExit(9)
if sys.argv[sys.argv.index("--dpi") + 1] != "72":
    print("wrong input DPI", file=sys.stderr)
    raise SystemExit(13)
if sys.argv[sys.argv.index("-l") + 1] != "eng":
    print("wrong language resource", file=sys.stderr)
    raise SystemExit(10)
if sys.argv[sys.argv.index("-c") + 1] != "tessedit_create_tsv=1":
    print("TSV output was not explicitly requested", file=sys.stderr)
    raise SystemExit(12)
behavior = {behavior!r}
if behavior == "success":
    if pathlib.Path(sys.argv[1]).name == "selection-000001.png":
        sys.stdout.write(HEADER + "\\n")
    else:
        sys.stdout.write(WORDS)
elif behavior == "malformed":
    sys.stdout.write("not tsv\\n")
elif behavior == "partial":
    sys.stdout.write(WORDS)
    print("temporary input: " + sys.argv[1], file=sys.stderr)
    raise SystemExit(2)
elif behavior == "mixed":
    if pathlib.Path(sys.argv[1]).name == "selection-000000.png":
        sys.stdout.write(WORDS)
        raise SystemExit(2)
    sys.stdout.write(HEADER + "\\n")
elif behavior == "timeout":
    time.sleep(2)
elif behavior == "timeout_closed_pipes":
    sys.stdout.close()
    sys.stderr.close()
    time.sleep(2)
elif behavior == "huge":
    sys.stdout.write("x" * 100000)
else:
    raise SystemExit(11)
"""
    path.write_text(textwrap.dedent(script), encoding="utf-8")
    path.chmod(0o700)
    return path


def _processor(
    tmp_path: Path,
    *,
    behavior: str = "success",
    version: str = "5.4.1",
    configuration: TesseractAdapterConfiguration | None = None,
    executable: str | Path | None = None,
    resource: Path | None = None,
) -> TesseractOCRProcessor:
    actual_executable = executable or _fake_tesseract(
        tmp_path, behavior=behavior, version=version
    )
    actual_resource = resource or _resource(tmp_path)
    return TesseractOCRProcessor(
        executable=actual_executable,
        language_bindings=(
            TesseractLanguageBinding(
                language="en",
                resource_name="eng",
                traineddata_path=actual_resource,
            ),
        ),
        configuration=configuration,
    )


def test__tesseract_configuration__is_bounded_and_immutable(
    tmp_path: Path,
) -> None:
    configuration = TesseractAdapterConfiguration(
        timeout_milliseconds=1_000,
        page_segmentation_mode=7,
        engine_mode=1,
    )
    processor = _processor(tmp_path, configuration=configuration)

    assert TESSERACT_ADAPTER_VERSION == "1"
    assert processor.version.startswith("1+")
    assert issubclass(OCRProcessor, Protocol)
    assert configuration.configuration_digest == (
        TesseractAdapterConfiguration(
            timeout_milliseconds=1_000,
            page_segmentation_mode=7,
            engine_mode=1,
        ).configuration_digest
    )
    with pytest.raises(FrozenInstanceError):
        configuration.page_segmentation_mode = 6  # type: ignore[misc]
    with pytest.raises(TesseractAdapterConfigurationError):
        TesseractAdapterConfiguration(timeout_milliseconds=True)  # type: ignore[arg-type]
    with pytest.raises(TesseractAdapterConfigurationError):
        TesseractAdapterConfiguration(page_segmentation_mode=14)
    with pytest.raises(TesseractAdapterConfigurationError, match="OSD"):
        TesseractAdapterConfiguration(page_segmentation_mode=1)
    with pytest.raises(TesseractAdapterConfigurationError):
        TesseractAdapterConfiguration(max_stdout_bytes=64_000_001)
    script_binding = TesseractLanguageBinding(
        language="und-Latn",
        resource_name="script/Latin",
        traineddata_path=tmp_path / "Latin.traineddata",
    )
    assert script_binding.resource_name == "script/Latin"
    with pytest.raises(TesseractAdapterConfigurationError):
        TesseractLanguageBinding(
            language="en",
            resource_name="../eng",
            traineddata_path=tmp_path / "eng.traineddata",
        )
    with pytest.raises(ValueError, match="one failure warning per selection"):
        _request(pages=2, max_total_warnings=1)


def test__tesseract_identity__includes_engine_configuration_and_resources(
    tmp_path: Path,
) -> None:
    request = _request()
    resource = _resource(tmp_path)
    first = _processor(
        tmp_path,
        version="5.4.1",
        resource=resource,
        configuration=TesseractAdapterConfiguration(page_segmentation_mode=6),
    )
    first_identity = first.identity_for(request)
    first_key = build_ocr_cache_key(
        request=request, processor_identity=first_identity
    )

    assert first_identity.backend_version.startswith(
        "5.4.1+version-output-sha256:"
    )
    assert "+binary-sha256:" in first_identity.backend_version
    assert first_identity.processor_version == first.version
    assert first_identity.language_resources[0].language == "en"
    assert first_identity.language_resources[0].resource_name == "eng"
    assert (
        first_identity.language_resources[0].identity_kind
        is OCRResourceIdentityKind.SHA256
    )
    assert first_identity.language_resources[0].resource_identity == (
        hashlib.sha256(b"traineddata-v1").hexdigest()
    )

    changed_binary = _processor(
        tmp_path,
        behavior="malformed",
        version="5.4.1",
        resource=resource,
        configuration=TesseractAdapterConfiguration(page_segmentation_mode=6),
    )
    changed_binary_key = build_ocr_cache_key(
        request=request,
        processor_identity=changed_binary.identity_for(request),
    )

    resource.write_bytes(b"traineddata-v2")
    changed_resource_identity = first.identity_for(request)
    changed_resource_key = build_ocr_cache_key(
        request=request,
        processor_identity=changed_resource_identity,
    )
    changed_version = _processor(
        tmp_path,
        version="5.5.0",
        resource=resource,
        configuration=TesseractAdapterConfiguration(page_segmentation_mode=6),
    )
    changed_version_key = build_ocr_cache_key(
        request=request,
        processor_identity=changed_version.identity_for(request),
    )
    changed_configuration = _processor(
        tmp_path,
        version="5.4.1",
        resource=resource,
        configuration=TesseractAdapterConfiguration(page_segmentation_mode=7),
    )
    changed_configuration_key = build_ocr_cache_key(
        request=request,
        processor_identity=changed_configuration.identity_for(request),
    )

    assert changed_binary_key != first_key
    assert changed_resource_key != first_key
    assert changed_version_key != changed_resource_key
    assert changed_configuration_key != changed_resource_key


def test__tesseract_processor__deduplicates_shared_backend_resources(
    tmp_path: Path,
) -> None:
    resource = _resource(tmp_path)
    processor = TesseractOCRProcessor(
        executable=_fake_tesseract(tmp_path),
        language_bindings=(
            TesseractLanguageBinding(
                language="en-US",
                resource_name="eng",
                traineddata_path=resource,
            ),
            TesseractLanguageBinding(
                language="en-GB",
                resource_name="eng",
                traineddata_path=resource,
            ),
        ),
        configuration=TesseractAdapterConfiguration(
            max_resource_bytes=len(b"traineddata-v1"),
            max_total_resource_bytes=len(b"traineddata-v1"),
        ),
    )
    request = _request(languages=("en-US", "en-GB"))

    result = processor.process(request)

    assert result.status is OCRResultStatus.COMPLETED
    assert [
        resource_identity.language
        for resource_identity in result.processor_identity.language_resources
    ] == ["en-US", "en-GB"]
    assert {
        resource_identity.resource_identity
        for resource_identity in result.processor_identity.language_resources
    } == {hashlib.sha256(b"traineddata-v1").hexdigest()}


@pytest.mark.parametrize("mode", tuple(OCROutputMode))
def test__tesseract_processor__maps_tsv_to_requested_evidence(
    tmp_path: Path,
    mode: OCROutputMode,
) -> None:
    request = _request(output_mode=mode)
    result = _processor(tmp_path).process(request)
    selection_result = result.selection_results[0]

    assert result.status is OCRResultStatus.COMPLETED
    assert selection_result.status is OCRSelectionStatus.COMPLETED
    assert not selection_result.warnings
    assert selection_result.failure is None
    if mode in (OCROutputMode.TOKENS, OCROutputMode.TOKENS_AND_LINES):
        assert [token.text for token in selection_result.tokens] == [
            "KOIOS",
            "OCR",
        ]
        assert [token.order for token in selection_result.tokens] == [0, 1]
        assert selection_result.tokens[0].pixel_bounding_box == (
            2.0,
            4.0,
            27.0,
            12.0,
        )
        assert selection_result.tokens[0].source_bounding_box == (
            2.0,
            4.0,
            27.0,
            12.0,
        )
        assert selection_result.tokens[0].confidence is not None
        assert selection_result.tokens[0].confidence.value == 0.96
    else:
        assert not selection_result.tokens
    if mode in (OCROutputMode.LINES, OCROutputMode.TOKENS_AND_LINES):
        assert [line.text for line in selection_result.lines] == ["KOIOS OCR"]
        assert selection_result.lines[0].pixel_bounding_box == (
            2.0,
            4.0,
            50.0,
            12.0,
        )
        assert selection_result.lines[0].confidence is not None
        assert selection_result.lines[0].confidence.value == pytest.approx(0.9)
    else:
        assert not selection_result.lines
    if mode is OCROutputMode.TOKENS_AND_LINES:
        assert selection_result.lines[0].token_ids == tuple(
            token.token_id for token in selection_result.tokens
        )
        assert all(token.line_order == 0 for token in selection_result.tokens)


def test__tesseract_processor__retains_native_text_as_separate_evidence(
    tmp_path: Path,
) -> None:
    request = _request(native_text=True)
    original_native_ids = request.selections[0].native_text_block_ids

    result = _processor(tmp_path).process(request)

    assert original_native_ids == ("native:0",)
    assert (
        result.request.selections[0].native_text_block_ids
        == original_native_ids
    )
    assert [token.text for token in result.selection_results[0].tokens] == [
        "KOIOS",
        "OCR",
    ]


def test__tesseract_processor__preserves_order_and_blank_success(
    tmp_path: Path,
) -> None:
    request = _request(pages=2)
    result = _processor(tmp_path).process(request)

    assert result.status is OCRResultStatus.COMPLETED
    assert [item.selection_id for item in result.selection_results] == [
        selection.selection_id for selection in request.selections
    ]
    assert result.selection_results[0].tokens
    assert not result.selection_results[1].tokens
    assert not result.selection_results[1].lines
    assert result.selection_results[1].status is OCRSelectionStatus.COMPLETED


def test__tesseract_processor__missing_executable_is_typed_failure(
    tmp_path: Path,
) -> None:
    request = _request(pages=2)
    processor = _processor(
        tmp_path,
        executable=tmp_path / "does-not-exist",
    )

    identity = processor.identity_for(request)
    result = processor.process(request)

    assert identity.backend_version == "unavailable"
    assert result.status is OCRResultStatus.FAILED
    assert all(
        item.failure is not None
        and item.failure.kind is OCRFailureKind.PROCESSOR_UNAVAILABLE
        and item.warnings[0].code == "ocr.tesseract.executable_unavailable"
        for item in result.selection_results
    )


def test__tesseract_processor__failure_respects_tight_warning_bounds(
    tmp_path: Path,
) -> None:
    request = _request(
        max_warning_message_characters=4,
        max_warning_evidence_entries=1,
    )
    processor = _processor(
        tmp_path,
        executable=tmp_path / "does-not-exist",
    )

    result = processor.process(request)

    selection_result = result.selection_results[0]
    assert selection_result.failure is not None
    assert selection_result.failure.kind is OCRFailureKind.PROCESSOR_UNAVAILABLE
    assert selection_result.failure.message == "Tess"
    assert selection_result.warnings[0].message == "Tess"


def test__tesseract_processor__unmapped_language_is_typed_failure(
    tmp_path: Path,
) -> None:
    request = _request(languages=("fr",))
    result = _processor(tmp_path).process(request)

    selection_result = result.selection_results[0]
    assert result.status is OCRResultStatus.FAILED
    assert selection_result.failure is not None
    assert selection_result.failure.kind is OCRFailureKind.UNSUPPORTED_LANGUAGE
    assert selection_result.warnings[0].code == (
        "ocr.tesseract.language_unmapped"
    )
    assert result.processor_identity.language_resources[0].language == "fr"


def test__tesseract_processor__missing_resource_is_typed_failure(
    tmp_path: Path,
) -> None:
    request = _request()
    missing = tmp_path / "missing.traineddata"
    result = _processor(tmp_path, resource=missing).process(request)

    selection_result = result.selection_results[0]
    assert result.status is OCRResultStatus.FAILED
    assert selection_result.failure is not None
    assert selection_result.failure.kind is OCRFailureKind.PROCESSOR_UNAVAILABLE
    assert selection_result.warnings[0].code == (
        "ocr.tesseract.resource_unavailable"
    )


def test__tesseract_processor__resource_limit_is_typed_failure(
    tmp_path: Path,
) -> None:
    processor = _processor(
        tmp_path,
        configuration=TesseractAdapterConfiguration(
            max_resource_bytes=4,
            max_total_resource_bytes=4,
        ),
    )
    result = processor.process(_request())

    selection_result = result.selection_results[0]
    assert result.status is OCRResultStatus.FAILED
    assert selection_result.failure is not None
    assert selection_result.failure.kind is OCRFailureKind.RESOURCE_LIMIT
    assert selection_result.warnings[0].code == "ocr.tesseract.resource_limit"


def test__tesseract_processor__invalid_output_is_typed_failure(
    tmp_path: Path,
) -> None:
    result = _processor(tmp_path, behavior="malformed").process(_request())

    selection_result = result.selection_results[0]
    assert result.status is OCRResultStatus.FAILED
    assert selection_result.failure is not None
    assert selection_result.failure.kind is OCRFailureKind.OUTPUT_INVALID
    assert selection_result.failure.retryable is False
    assert selection_result.warnings[0].code == "ocr.tesseract.output_invalid"


def test__tesseract_processor__nonzero_with_output_is_partial(
    tmp_path: Path,
) -> None:
    result = _processor(tmp_path, behavior="partial").process(_request())

    selection_result = result.selection_results[0]
    assert result.status is OCRResultStatus.PARTIAL
    assert selection_result.status is OCRSelectionStatus.PARTIAL
    assert selection_result.tokens
    assert selection_result.lines
    assert selection_result.failure is not None
    assert selection_result.failure.kind is OCRFailureKind.PROCESSOR_ERROR
    assert selection_result.failure.retryable is True
    assert selection_result.warnings[0].code == "ocr.tesseract.process_error"
    assert dict(selection_result.warnings[0].evidence) == {"returncode": "2"}
    assert all(
        selection_result.warnings[0].warning_id in output.warning_ids
        for output in (*selection_result.tokens, *selection_result.lines)
    )


def test__tesseract_processor__preserves_mixed_selection_outcomes(
    tmp_path: Path,
) -> None:
    result = _processor(tmp_path, behavior="mixed").process(_request(pages=2))

    assert result.status is OCRResultStatus.PARTIAL
    assert [item.status for item in result.selection_results] == [
        OCRSelectionStatus.PARTIAL,
        OCRSelectionStatus.COMPLETED,
    ]
    assert result.selection_results[0].tokens
    assert not result.selection_results[1].tokens


def test__tesseract_processor__failure_identity_excludes_temporary_paths(
    tmp_path: Path,
) -> None:
    request = _request()
    processor = _processor(tmp_path, behavior="partial")

    first = processor.process(request)
    second = processor.process(request)

    assert first.result_id == second.result_id
    assert first.selection_results[0].selection_result_id == (
        second.selection_results[0].selection_result_id
    )
    assert first.selection_results[0].warnings[0].warning_id == (
        second.selection_results[0].warnings[0].warning_id
    )


@pytest.mark.parametrize("behavior", ("timeout", "timeout_closed_pipes"))
def test__tesseract_processor__timeout_is_bounded_typed_failure(
    tmp_path: Path,
    behavior: str,
) -> None:
    processor = _processor(
        tmp_path,
        behavior=behavior,
        configuration=TesseractAdapterConfiguration(timeout_milliseconds=50),
    )
    started = time.monotonic()
    result = processor.process(_request())
    elapsed = time.monotonic() - started

    selection_result = result.selection_results[0]
    assert elapsed < 1.5
    assert result.status is OCRResultStatus.FAILED
    assert selection_result.failure is not None
    assert selection_result.failure.kind is OCRFailureKind.RESOURCE_LIMIT
    assert selection_result.failure.retryable is True
    assert selection_result.warnings[0].code == "ocr.tesseract.timeout"


def test__tesseract_processor__aggregate_limit_is_typed_failure(
    tmp_path: Path,
) -> None:
    result = _processor(tmp_path).process(_request(max_total_tokens=1))

    selection_result = result.selection_results[0]
    assert result.status is OCRResultStatus.FAILED
    assert selection_result.failure is not None
    assert selection_result.failure.kind is OCRFailureKind.RESOURCE_LIMIT
    assert selection_result.warnings[0].code == (
        "ocr.tesseract.aggregate_result_limit"
    )


def test__tesseract_processor__capture_limit_is_typed_failure(
    tmp_path: Path,
) -> None:
    processor = _processor(
        tmp_path,
        behavior="huge",
        configuration=TesseractAdapterConfiguration(max_stdout_bytes=1_024),
    )
    result = processor.process(_request())

    selection_result = result.selection_results[0]
    assert result.status is OCRResultStatus.FAILED
    assert selection_result.failure is not None
    assert selection_result.failure.kind is OCRFailureKind.RESOURCE_LIMIT
    assert selection_result.warnings[0].code == "ocr.tesseract.output_limit"


def test__tesseract_processor__optional_real_engine_smoke() -> None:
    executable = os.environ.get("KOIOS_TESSERACT_EXECUTABLE")
    resource = os.environ.get("KOIOS_TESSERACT_ENG_TRAINEDDATA")
    if executable is None or resource is None:
        pytest.skip("real Tesseract smoke test is not configured")
    processor = TesseractOCRProcessor(
        executable=Path(executable),
        language_bindings=(
            TesseractLanguageBinding(
                language="en",
                resource_name="eng",
                traineddata_path=Path(resource),
            ),
        ),
    )

    result = processor.process(_request())

    assert result.status is OCRResultStatus.COMPLETED
    assert result.processor_identity.backend_version != "unavailable"


def test__ocr_fixture__is_exact_and_redistributable() -> None:
    content = FIXTURE.read_bytes()
    assert len(content) == 238
    assert hashlib.sha256(content).hexdigest() == FIXTURE_SHA256
    assert content.startswith(b"\x89PNG\r\n\x1a\n")
