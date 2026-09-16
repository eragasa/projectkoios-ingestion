from __future__ import annotations

import hashlib
import typing
import zlib
from dataclasses import FrozenInstanceError, replace

import pytest
from projectkoios.ingestion import (
    EquationCandidate,
    EquationCandidateKind,
    EquationEvidenceStatus,
    EquationSymbolConfidenceCoverage,
    EquationSymbolStatus,
    EquationTranscriptionConfidence,
    EquationTranscriptionConfiguration,
    EquationTranscriptionFailure,
    EquationTranscriptionFailureKind,
    EquationTranscriptionFormat,
    EquationTranscriptionLimitError,
    EquationTranscriptionProcessor,
    EquationTranscriptionProcessorIdentity,
    EquationTranscriptionProposal,
    EquationTranscriptionRequest,
    EquationTranscriptionResourceIdentity,
    EquationTranscriptionResourceIdentityKind,
    EquationTranscriptionResult,
    EquationTranscriptionSelection,
    EquationTranscriptionSelectionResult,
    EquationTranscriptionStatus,
    EquationTranscriptionSymbol,
    EquationTranscriptionWarning,
    RegionRenderConfiguration,
    RenderedRegion,
    SourceDocument,
    SourceSpan,
    WarningSeverity,
    build_equation_transcription_cache_key,
)


def _png(suffix: bytes = b"") -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return (
            len(payload).to_bytes(4, "big")
            + kind
            + payload
            + checksum.to_bytes(4, "big")
        )

    width = 100
    height = 50
    fill = sum(suffix) % 256
    header = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes((8, 2, 0, 0, 0))
    )
    row = b"\x00" + bytes((fill, 0, 0)) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def _candidate(
    *,
    suffix: bytes = b"",
    span_box: tuple[float, float, float, float] = (
        20.0,
        30.0,
        100.0,
        60.0,
    ),
) -> EquationCandidate:
    source = SourceDocument.from_bytes(
        b"synthetic-equation-pdf" + suffix,
        source_id="article:equation-transcription",
        media_type="application/pdf",
        locator="memory://equation-transcription.pdf",
    )
    region = RenderedRegion.create(
        source=source,
        page_index=0,
        printed_page_label="1",
        source_bounding_box=(10.0, 20.0, 110.0, 70.0),
        effective_source_bounding_box=(10.0, 20.0, 110.0, 70.0),
        pixel_to_source_matrix=(1.0, 0.0, 0.0, 1.0, 10.0, 20.0),
        page_rotation_degrees=0,
        selection_was_full_page=False,
        configuration=RegionRenderConfiguration(resolution_dpi=72),
        content=_png(suffix),
        width_pixels=100,
        height_pixels=50,
        processor_name="synthetic-renderer",
        processor_version="1",
        backend_name="synthetic-pdf",
        backend_version="1",
    )
    span = SourceSpan(
        source_id=source.source_id,
        source_blob_id=source.blob_id,
        page_index=0,
        bounding_box=span_box,
        source_object_id="text:block:1",
    )
    return EquationCandidate.create(
        detection_input_id="equation-input:synthetic",
        kind=EquationCandidateKind.DISPLAY,
        source_block_id="block:equation:1",
        source_spans=(span,),
        raw_text="E = m c^2    (1)",
        source_label="(1)",
        rendered_region=region,
        preceding_context=None,
        following_context=None,
        confidence=0.9,
        evidence_status=EquationEvidenceStatus.PROPOSED,
        evidence=(("detection_method", "synthetic"),),
        warning_ids=(),
        processor_name="synthetic-detector",
        processor_version="1",
        configuration_digest="detector-configuration:1",
    )


def _configuration(
    **changes: object,
) -> EquationTranscriptionConfiguration:
    values: dict[str, object] = {
        "formats": (
            EquationTranscriptionFormat.LATEX,
            EquationTranscriptionFormat.MATHML,
        ),
    }
    values.update(changes)
    return EquationTranscriptionConfiguration(**values)  # type: ignore[arg-type]


def _request(
    *,
    suffix: bytes = b"",
    configuration: EquationTranscriptionConfiguration | None = None,
) -> EquationTranscriptionRequest:
    selection = EquationTranscriptionSelection.from_candidate(
        _candidate(suffix=suffix)
    )
    return EquationTranscriptionRequest.create(
        (selection,), configuration=configuration or _configuration()
    )


def _identity(
    *,
    processor_version: str = "1",
    resource_suffix: str = "v1",
) -> EquationTranscriptionProcessorIdentity:
    return EquationTranscriptionProcessorIdentity(
        processor_name="synthetic-equation-transcriber",
        processor_version=processor_version,
        backend_name="synthetic-math-recognizer",
        backend_version="2",
        resources=(
            EquationTranscriptionResourceIdentity(
                resource_name="model",
                identity_kind=(
                    EquationTranscriptionResourceIdentityKind.EXPLICIT
                ),
                resource_identity=f"model-{resource_suffix}",
            ),
            EquationTranscriptionResourceIdentity(
                resource_name="vocabulary",
                identity_kind=EquationTranscriptionResourceIdentityKind.SHA256,
                resource_identity=hashlib.sha256(
                    f"vocabulary-{resource_suffix}".encode()
                ).hexdigest(),
            ),
        ),
    )


def _confidence(value: float) -> EquationTranscriptionConfidence:
    return EquationTranscriptionConfidence(
        value=value,
        method="synthetic-symbol-probability",
        method_version="1",
        scale="unit_interval",
    )


def _complete_proposal(
    request: EquationTranscriptionRequest,
    identity: EquationTranscriptionProcessorIdentity,
    output_format: EquationTranscriptionFormat,
) -> tuple[
    EquationTranscriptionProposal, tuple[EquationTranscriptionWarning, ...]
]:
    selection = request.selections[0]
    configuration = request.configuration
    text = (
        r"E=mc^2"
        if output_format is EquationTranscriptionFormat.LATEX
        else "<math>E=mc^2</math>"
    )
    low_warning = EquationTranscriptionWarning.create(
        selection_id=selection.selection_id,
        output_format=output_format,
        code="equation_transcription.low_confidence_symbol",
        severity=WarningSeverity.WARNING,
        message="One output span has low adapter confidence",
        evidence=(("method", "synthetic"),),
    )
    symbols = tuple(
        EquationTranscriptionSymbol.create(
            selection_id=selection.selection_id,
            output_format=output_format,
            start_offset=index,
            end_offset=index + 1,
            text=character,
            confidence=_confidence(0.4 if character == "m" else 0.95),
            warning_ids=(low_warning.warning_id,) if character == "m" else (),
            configuration=configuration,
            processor_identity=identity,
        )
        for index, character in enumerate(text)
    )
    proposal = EquationTranscriptionProposal.create(
        selection=selection,
        output_format=output_format,
        text=text,
        confidence=_confidence(0.9),
        symbol_confidence_coverage=(EquationSymbolConfidenceCoverage.COMPLETE),
        symbols=symbols,
        warning_ids=(low_warning.warning_id,),
        configuration=configuration,
        processor_identity=identity,
    )
    return proposal, (low_warning,)


def _completed_result() -> EquationTranscriptionResult:
    request = _request()
    identity = _identity()
    latex, latex_warnings = _complete_proposal(
        request, identity, EquationTranscriptionFormat.LATEX
    )
    mathml, mathml_warnings = _complete_proposal(
        request, identity, EquationTranscriptionFormat.MATHML
    )
    selection_result = EquationTranscriptionSelectionResult.create(
        selection=request.selections[0],
        configuration=request.configuration,
        status=EquationTranscriptionStatus.COMPLETED,
        proposals=(latex, mathml),
        warnings=latex_warnings + mathml_warnings,
        processor_identity=identity,
    )
    return EquationTranscriptionResult.create(
        request=request,
        selection_results=(selection_result,),
        processor_identity=identity,
    )


def test__equation_transcription__retains_source_and_marks_low_confidence() -> (
    None
):
    result = _completed_result()

    assert result.status is EquationTranscriptionStatus.COMPLETED
    assert tuple(
        proposal.output_format
        for proposal in result.selection_results[0].proposals
    ) == (
        EquationTranscriptionFormat.LATEX,
        EquationTranscriptionFormat.MATHML,
    )
    low_symbols = tuple(
        symbol
        for proposal in result.selection_results[0].proposals
        for symbol in proposal.symbols
        if symbol.status is EquationSymbolStatus.LOW_CONFIDENCE
    )
    assert low_symbols
    assert all(symbol.warning_ids for symbol in low_symbols)
    selection = result.request.selections[0]
    assert selection.candidate.raw_text == "E = m c^2    (1)"
    assert selection.rendered_region.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert (
        selection.rendered_region.content_sha256
        == hashlib.sha256(selection.rendered_region.content).hexdigest()
    )
    assert not hasattr(EquationSymbolStatus, "ACCEPTED")


def test__equation_transcription__unavailable_confidence_is_partial() -> None:
    request = _request()
    identity = _identity()
    selection = request.selections[0]
    warning = EquationTranscriptionWarning.create(
        selection_id=selection.selection_id,
        output_format=EquationTranscriptionFormat.LATEX,
        code="equation_transcription.symbol_confidence_unavailable",
        severity=WarningSeverity.WARNING,
        message="Backend supplied no symbol confidence",
    )
    proposal = EquationTranscriptionProposal.create(
        selection=selection,
        output_format=EquationTranscriptionFormat.LATEX,
        text=r"E=mc^2",
        confidence=None,
        symbol_confidence_coverage=(
            EquationSymbolConfidenceCoverage.UNAVAILABLE
        ),
        symbols=(),
        warning_ids=(warning.warning_id,),
        configuration=request.configuration,
        processor_identity=identity,
    )
    failure = EquationTranscriptionFailure.create(
        selection_id=selection.selection_id,
        kind=EquationTranscriptionFailureKind.OUTPUT_INCOMPLETE,
        message="Symbol confidence was unavailable",
        retryable=False,
        warning_ids=(warning.warning_id,),
    )
    selection_result = EquationTranscriptionSelectionResult.create(
        selection=selection,
        configuration=request.configuration,
        status=EquationTranscriptionStatus.PARTIAL,
        proposals=(proposal,),
        warnings=(warning,),
        failure=failure,
        processor_identity=identity,
    )
    result = EquationTranscriptionResult.create(
        request=request,
        selection_results=(selection_result,),
        processor_identity=identity,
    )

    assert result.status is EquationTranscriptionStatus.PARTIAL
    assert proposal.symbol_confidence_coverage is (
        EquationSymbolConfidenceCoverage.UNAVAILABLE
    )
    assert result.request.selections[0].rendered_region.content


def test__equation_transcription__retains_typed_failure() -> None:
    request = _request()
    identity = _identity()
    selection = request.selections[0]
    warning = EquationTranscriptionWarning.create(
        selection_id=selection.selection_id,
        code="equation_transcription.processor_unavailable",
        severity=WarningSeverity.ERROR,
        message="Synthetic backend unavailable",
    )
    failure = EquationTranscriptionFailure.create(
        selection_id=selection.selection_id,
        kind=EquationTranscriptionFailureKind.PROCESSOR_UNAVAILABLE,
        message="Synthetic backend unavailable",
        retryable=True,
        warning_ids=(warning.warning_id,),
    )
    selection_result = EquationTranscriptionSelectionResult.create(
        selection=selection,
        configuration=request.configuration,
        status=EquationTranscriptionStatus.FAILED,
        warnings=(warning,),
        failure=failure,
        processor_identity=identity,
    )
    result = EquationTranscriptionResult.create(
        request=request,
        selection_results=(selection_result,),
        processor_identity=identity,
    )

    assert result.status is EquationTranscriptionStatus.FAILED
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.retryable is True


def test__equation_transcription__cache_identity_is_complete() -> None:
    request = _request()
    identity = _identity()
    base = build_equation_transcription_cache_key(
        request=request, processor_identity=identity
    )

    assert base != build_equation_transcription_cache_key(
        request=request,
        processor_identity=_identity(processor_version="2"),
    )
    assert base != build_equation_transcription_cache_key(
        request=request,
        processor_identity=_identity(resource_suffix="v2"),
    )
    assert base != build_equation_transcription_cache_key(
        request=_request(suffix=b"changed"),
        processor_identity=identity,
    )
    changed_configuration = _configuration(low_confidence_threshold=0.5)
    assert base != build_equation_transcription_cache_key(
        request=_request(configuration=changed_configuration),
        processor_identity=identity,
    )


def test__equation_transcription__rejects_resource_relabeling() -> None:
    result = _completed_result()

    with pytest.raises(ValueError, match="processor identity"):
        EquationTranscriptionResult.create(
            request=result.request,
            selection_results=result.selection_results,
            processor_identity=_identity(resource_suffix="other"),
        )


def test__equation_transcription__rejects_symbol_status_tampering() -> None:
    request = _request()
    identity = _identity()
    selection = request.selections[0]
    warning = EquationTranscriptionWarning.create(
        selection_id=selection.selection_id,
        output_format=EquationTranscriptionFormat.LATEX,
        code="equation_transcription.low_confidence_symbol",
        severity=WarningSeverity.WARNING,
        message="Low confidence",
    )
    symbol = EquationTranscriptionSymbol.create(
        selection_id=selection.selection_id,
        output_format=EquationTranscriptionFormat.LATEX,
        start_offset=0,
        end_offset=1,
        text="x",
        confidence=_confidence(0.2),
        warning_ids=(warning.warning_id,),
        configuration=request.configuration,
        processor_identity=identity,
    )
    assert symbol.status is EquationSymbolStatus.LOW_CONFIDENCE
    with pytest.raises(ValueError, match="symbol ID"):
        replace(symbol, status=EquationSymbolStatus.PROPOSED)


def test__equation_transcription__rejects_inexact_symbol_ranges() -> None:
    request = _request()
    identity = _identity()
    selection = request.selections[0]
    symbol = EquationTranscriptionSymbol.create(
        selection_id=selection.selection_id,
        output_format=EquationTranscriptionFormat.LATEX,
        start_offset=0,
        end_offset=1,
        text="x",
        confidence=_confidence(0.9),
        warning_ids=(),
        configuration=request.configuration,
        processor_identity=identity,
    )

    with pytest.raises(ValueError, match="exact output range"):
        EquationTranscriptionProposal.create(
            selection=selection,
            output_format=EquationTranscriptionFormat.LATEX,
            text="y",
            confidence=_confidence(0.9),
            symbol_confidence_coverage=(
                EquationSymbolConfidenceCoverage.COMPLETE
            ),
            symbols=(symbol,),
            warning_ids=(),
            configuration=request.configuration,
            processor_identity=identity,
        )


def test__equation_transcription__enforces_source_image_limits() -> None:
    selection = EquationTranscriptionSelection.from_candidate(_candidate())
    configuration = _configuration(max_total_pixels=1)

    with pytest.raises(
        EquationTranscriptionLimitError, match="max_total_pixels"
    ):
        EquationTranscriptionRequest.create(
            (selection,), configuration=configuration
        )


def test__equation_transcription__requires_candidate_image_containment() -> (
    None
):
    candidate = _candidate(span_box=(0.0, 0.0, 5.0, 5.0))

    with pytest.raises(ValueError, match="does not contain"):
        EquationTranscriptionSelection.from_candidate(candidate)


def test__equation_transcription__is_immutable_and_deterministic() -> None:
    first = _completed_result()
    second = _completed_result()

    assert first == second
    assert first.result_id == second.result_id
    assert first.cache_key == second.cache_key
    with pytest.raises(FrozenInstanceError):
        first.result_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="result ID"):
        replace(first, result_id="changed")
    with pytest.raises(ValueError, match="request ID"):
        replace(first.request, request_id="changed")


def test__equation_transcription__protocol_is_runtime_resolvable() -> None:
    hints = typing.get_type_hints(EquationTranscriptionProcessor.process)
    assert hints["request"] is EquationTranscriptionRequest
    assert hints["return"] is EquationTranscriptionResult
