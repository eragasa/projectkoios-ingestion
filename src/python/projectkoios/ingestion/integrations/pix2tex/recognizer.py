"""Bounded Pix2Tex CLI equation-recognition adapter."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

from projectkoios.ingestion.equations.assembly.model import EquationAssembly
from projectkoios.ingestion.equations.assembly.result import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.equations.image.factory import EquationImage
from projectkoios.ingestion.equations.latex import EquationLatex
from projectkoios.ingestion.equations.mathml import EquationMathML
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.base import (
    AbstractEquationRecognizer,
)
from projectkoios.ingestion.equations.recognition.error import (
    EquationRecognitionError,
)
from projectkoios.ingestion.equations.recognition.identity import (
    EQUATION_RECOGNITION_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.recognition.processor.identity import (
    EquationRecognitionProcessorIdentity,
)
from projectkoios.ingestion.equations.recognition.proposal import (
    EquationRecognitionProposal,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from projectkoios.ingestion.equations.recognition.resource import (
    EquationRecognitionResource,
)
from projectkoios.ingestion.equations.recognition.status import (
    EquationRecognitionStatus,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.pix2tex.invocation.error import (
    Pix2TexInvocationError,
)
from projectkoios.ingestion.integrations.pix2tex.invocation.output import (
    Pix2TexInvocationOutput,
)
from projectkoios.ingestion.integrations.pix2tex.invocation.request import (
    Pix2TexInvocationRequest,
)
from projectkoios.ingestion.integrations.pix2tex.invocation.result import (
    Pix2TexInvocationResult,
)
from projectkoios.ingestion.integrations.pix2tex.output_policy import (
    pix2tex_output_quality_warning_codes,
)
from projectkoios.ingestion.integrations.pix2tex.policy import (
    is_pix2tex_primary_recognition_candidate,
    pix2tex_primary_recognition_ineligibility_reasons,
)
from projectkoios.ingestion.integrations.pix2tex.resource import (
    Pix2TexResourceBinding,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.verifier import SHA256Verifier


class Pix2TexCliEquationRecognizer(AbstractEquationRecognizer):
    """Bounded external Pix2Tex effect worker with explicit identities."""

    MAX_OUTPUT_BYTES: ClassVar[int] = 8_000_000
    MAX_LATEX_CHARACTERS: ClassVar[int] = 16_384

    def __init__(
        self,
        executable: Path,
        *,
        backend_version: str,
        resources: tuple[Pix2TexResourceBinding, ...],
        temperature: float = 0.01,
        timeout_seconds: int = 900,
    ) -> None:
        self.executable = executable.expanduser().resolve()
        if not self.executable.is_file() or not os.access(
            self.executable, os.X_OK
        ):
            raise ValueError("pix2tex executable is not executable")
        if timeout_seconds <= 0 or timeout_seconds > 3600:
            raise ValueError("pix2tex timeout must be in (0, 3600]")
        self.timeout_seconds = timeout_seconds
        if type(resources) is not tuple or any(
            type(binding) is not Pix2TexResourceBinding for binding in resources
        ):
            raise TypeError("Pix2Tex resources must be named bindings")
        resource_values = tuple(
            EquationRecognitionResource(
                name=binding.name,
                path=str(binding.path.expanduser().resolve()),
                sha256=SHA256Fingerprinter.fingerprint(
                    content=binding.path.expanduser().resolve().read_bytes()
                ),
                byte_size=(binding.path.expanduser().resolve().stat().st_size),
            )
            for binding in sorted(resources, key=lambda item: item.name)
        )
        executable_content = self.executable.read_bytes()
        self._identity = EquationRecognitionProcessorIdentity(
            processor_name="pix2tex-cli-equation-recognizer",
            processor_version="5",
            backend_name="pix2tex",
            backend_version=backend_version,
            executable_sha256=SHA256Fingerprinter.fingerprint(
                content=executable_content
            ),
            executable_semantic_sha256=_executable_semantic_sha256(
                executable_content
            ),
            resources=resource_values,
            temperature=temperature,
        )

    @property
    def identity(self) -> EquationRecognitionProcessorIdentity:
        return self._identity

    def action(
        self,
        *,
        request: EquationRecognitionRequest,
    ) -> EquationRecognitionArtifact:
        """Execute one exact externally requested Pix2Tex effect."""

        if type(request) is not EquationRecognitionRequest:
            raise TypeError("request must be an EquationRecognitionRequest")
        if request.processor_identity != self.identity:
            raise EquationRecognitionError(
                "equation-recognition request targets another processor"
            )
        artifact = request.assembly_artifact
        try:
            return self._recognize(artifact)
        except EquationRecognitionError:
            raise
        except (OSError, UnicodeError, ValueError) as error:
            raise EquationRecognitionError(
                "equation-recognition transition failed"
            ) from error

    def _recognize(
        self,
        artifact: EquationAssemblyResult,
    ) -> EquationRecognitionArtifact:
        if self.executable.is_symlink() or not self.executable.is_file():
            raise EquationRecognitionError(
                "equation-recognition executable path became unsafe"
            )
        if not SHA256Verifier.verify(
            content=self.executable.read_bytes(),
            expected=self.identity.executable_sha256,
        ):
            raise EquationRecognitionError(
                "equation-recognition executable changed after planning"
            )
        for resource in self.identity.resources:
            path = Path(resource.path)
            if path.is_symlink() or not path.is_file():
                raise EquationRecognitionError(
                    "equation-recognition resource path became unsafe"
                )
            content = path.read_bytes()
            if len(content) != resource.byte_size or not SHA256Verifier.verify(
                content=content, expected=resource.sha256
            ):
                raise EquationRecognitionError(
                    "equation-recognition resource changed after planning"
                )
        selected = tuple(
            assembly
            for assembly in artifact.assemblies
            if is_pix2tex_primary_recognition_candidate(assembly)
        )
        invocation = Pix2TexInvocationResult(
            diagnostic=b"",
            outputs=(),
        )
        invocation_failure: Pix2TexInvocationError | None = None
        if selected:
            try:
                invocation = self._invoke(
                    request=Pix2TexInvocationRequest(assemblies=selected)
                )
            except Pix2TexInvocationError as error:
                invocation_failure = error
        invocation_exit_code = (
            invocation_failure.exit_code
            if invocation_failure is not None
            else 0
        )
        invocation_diagnostic = (
            invocation_failure.diagnostic
            if invocation_failure is not None
            else invocation.diagnostic
        )
        latex_by_id = {
            output.assembly_id: output.latex for output in invocation.outputs
        }
        proposals = tuple(
            _recognition_proposal(
                assembly,
                latex=latex_by_id.get(assembly.assembly_id),
                exit_code=invocation_exit_code,
                processor_identity_digest=self.identity.identity_digest,
            )
            for assembly in artifact.assemblies
        )
        diagnostic_sha256 = SHA256Fingerprinter.fingerprint(
            content=invocation_diagnostic
        )
        artifact_id = stable_id(
            "equation-recognition-artifact",
            EQUATION_RECOGNITION_CONTRACT_VERSION,
            artifact.artifact_id,
            self.identity.identity_digest,
            tuple(item.proposal_id for item in proposals),
            invocation_exit_code,
            len(invocation_diagnostic),
            diagnostic_sha256,
        )
        return EquationRecognitionArtifact(
            artifact_id=artifact_id,
            assembly_artifact_id=artifact.artifact_id,
            processor_identity=self.identity,
            proposals=proposals,
            invocation_exit_code=invocation_exit_code,
            diagnostic_byte_size=len(invocation_diagnostic),
            diagnostic_sha256=diagnostic_sha256,
        )

    def _invoke(
        self,
        *,
        request: Pix2TexInvocationRequest,
    ) -> Pix2TexInvocationResult:
        with tempfile.TemporaryDirectory(prefix="koios-pix2tex-") as directory:
            root = Path(directory)
            paths: dict[Path, str] = {}
            for index, assembly in enumerate(request.assemblies):
                suffix = assembly.assembly_id.rsplit(":", 1)[-1]
                path = root / f"{index:04d}-{suffix}.png"
                path.write_bytes(assembly.rendered_region.content)
                paths[path.resolve()] = assembly.assembly_id
            stdout_path = root / "stdout.txt"
            stderr_path = root / "stderr.txt"
            environment = dict(os.environ)
            environment["NO_ALBUMENTATIONS_UPDATE"] = "1"
            command = [
                str(self.executable),
                "--no-cuda",
                "--temperature",
                str(self.identity.temperature),
                *(str(path) for path in paths),
            ]
            with (
                stdout_path.open("wb") as stdout,
                stderr_path.open("wb") as stderr,
            ):
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    env=environment,
                )
                try:
                    exit_code = process.wait(timeout=self.timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    exit_code = 124
            if stdout_path.stat().st_size > self.MAX_OUTPUT_BYTES:
                raise ValueError("pix2tex output exceeds the limit")
            if (
                stderr_path.stat().st_size
                > Pix2TexInvocationResult.MAX_DIAGNOSTIC_BYTES
            ):
                raise ValueError("pix2tex diagnostics exceed the limit")
            diagnostic = stderr_path.read_bytes()
            if exit_code != 0:
                raise Pix2TexInvocationError(
                    exit_code=exit_code,
                    diagnostic=diagnostic,
                )
            output = stdout_path.read_text(encoding="utf-8", errors="strict")
            results: dict[str, str] = {}
            for line in output.splitlines():
                name, separator, latex = line.partition(": ")
                if not separator:
                    continue
                path = Path(name).resolve()
                assembly_id = paths.get(path)
                if assembly_id is None or assembly_id in results:
                    raise ValueError(
                        "pix2tex returned an unexpected image path"
                    )
                text = latex.strip()
                if text:
                    results[assembly_id] = text
            return Pix2TexInvocationResult(
                diagnostic=diagnostic,
                outputs=tuple(
                    Pix2TexInvocationOutput(
                        assembly_id=assembly.assembly_id,
                        latex=results[assembly.assembly_id],
                    )
                    for assembly in request.assemblies
                    if assembly.assembly_id in results
                ),
            )


def _recognition_proposal(
    assembly: EquationAssembly,
    *,
    latex: str | None,
    exit_code: int,
    processor_identity_digest: str,
) -> EquationRecognitionProposal:
    warnings: list[str] = []
    failure: str | None = None
    mathml_content: str | None = None
    mathml_processor_identity: str | None = None
    mathml_processor_version: str | None = None
    latex_equation: EquationLatex | None = None
    mathml_equation: EquationMathML | None = None
    ineligibility_reasons = pix2tex_primary_recognition_ineligibility_reasons(
        assembly
    )
    if ineligibility_reasons:
        status = EquationRecognitionStatus.NOT_REQUESTED
        warnings.append("recognition_not_requested_for_non_primary_evidence")
        warnings.extend(
            f"recognition_ineligible:{reason}"
            for reason in ineligibility_reasons
        )
    elif exit_code != 0 or latex is None:
        status = EquationRecognitionStatus.FAILED
        warnings.append("pix2tex_failed")
        failure = (
            f"pix2tex exit code {exit_code}; no bounded proposal was retained"
        )
        latex = None
    else:
        status = EquationRecognitionStatus.PROPOSED
        warnings.append("recognition_confidence_unavailable")
        equation_image = EquationImage.from_bytes(
            content=assembly.rendered_region.content,
            source_ids=(assembly.rendered_region.region_id,),
        )
        latex_equation = EquationLatex(
            source_ids=(equation_image.equation_id,),
            latex=latex,
        )
        quality_warnings = pix2tex_output_quality_warning_codes(
            latex,
            assembly.sanitized_native_text,
            assembly.source_labels,
        )
        if not _latex_is_well_formed(latex):
            warnings.append("latex_structure_suspect")
        warnings.extend(quality_warnings)
        try:
            import latex2mathml
            from latex2mathml.converter import convert

            mathml_processor_version = latex2mathml.__version__
            mathml_processor_identity = stable_id(
                "equation-mathml-processor",
                "latex2mathml",
                mathml_processor_version,
            )
            mathml_content = convert(latex)
            mathml_equation = EquationMathML(
                source_ids=(latex_equation.equation_id,),
                mathml=mathml_content,
            )
        except Exception:  # latex2mathml exposes multiple parser exceptions
            mathml_content = None
            mathml_processor_identity = None
            mathml_processor_version = None
            warnings.append("mathml_conversion_unavailable")
    proposal_id = stable_id(
        "equation-recognition-proposal",
        EQUATION_RECOGNITION_CONTRACT_VERSION,
        assembly.assembly_id,
        status,
        latex,
        mathml_content,
        tuple(warnings),
        failure,
        processor_identity_digest,
    )
    return EquationRecognitionProposal(
        proposal_id=proposal_id,
        assembly_id=assembly.assembly_id,
        status=status,
        latex=latex_equation,
        mathml=mathml_equation,
        mathml_processor_identity=mathml_processor_identity,
        mathml_processor_version=mathml_processor_version,
        warning_codes=tuple(warnings),
        failure_message=failure,
        processor_identity_digest=processor_identity_digest,
    )


def _latex_is_well_formed(value: str) -> bool:
    if (
        not value
        or len(value) > Pix2TexCliEquationRecognizer.MAX_LATEX_CHARACTERS
    ):
        return False
    structural_warnings = {
        "latex_brace_mismatch",
        "latex_left_right_delimiter_mismatch",
        "latex_environment_mismatch",
    }
    return structural_warnings.isdisjoint(
        pix2tex_output_quality_warning_codes(value, "")
    )


def _executable_semantic_sha256(content: bytes) -> str:
    if content.startswith(b"#!"):
        _, separator, remainder = content.partition(b"\n")
        content = b"#!python\n" + remainder if separator else b"#!python"
    return SHA256Fingerprinter.fingerprint(content=content)
