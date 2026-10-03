from __future__ import annotations

import hashlib

from projectkoios.ingestion.equations.assembly.identity import (
    EQUATION_ASSEMBLY_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.assembly.result import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.identity import (
    EQUATION_RECOGNITION_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.recognition.processor.identity import (
    EquationRecognitionProcessorIdentity,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from projectkoios.ingestion.equations.recognition.resource import (
    EquationRecognitionResource,
)
from projectkoios.ingestion.identity import stable_id


def assembly(*, name: str = "fixture") -> EquationAssemblyResult:
    source_id = f"source:{name}"
    source_hash = hashlib.sha256(source_id.encode()).hexdigest()
    artifact_id = stable_id(
        "equation-assembly-artifact",
        EQUATION_ASSEMBLY_CONTRACT_VERSION,
        source_id,
        source_hash,
        f"document:{name}",
        f"detection:{name}",
        (),
    )
    return EquationAssemblyResult(
        artifact_id=artifact_id,
        source_id=source_id,
        source_content_hash=source_hash,
        document_id=f"document:{name}",
        detection_result_id=f"detection:{name}",
        assemblies=(),
    )


def processor(*, name: str = "fixture") -> EquationRecognitionProcessorIdentity:
    return EquationRecognitionProcessorIdentity(
        processor_name="bounded-recognizer",
        processor_version="1",
        backend_name="test",
        backend_version="1",
        executable_sha256="a" * 64,
        executable_semantic_sha256="b" * 64,
        resources=(
            EquationRecognitionResource(
                name="model",
                path=f"/bounded/{name}/model",
                sha256="c" * 64,
                byte_size=1,
            ),
        ),
        temperature=0.01,
    )


def request(*, name: str = "fixture") -> EquationRecognitionRequest:
    return EquationRecognitionRequest.create(
        assembly_artifact=assembly(name=name),
        processor_identity=processor(name=name),
    )


def artifact(
    *,
    recognition_request: EquationRecognitionRequest | None = None,
    name: str = "fixture",
) -> EquationRecognitionArtifact:
    actual_request = recognition_request or request(name=name)
    diagnostic_sha256 = hashlib.sha256(b"").hexdigest()
    artifact_id = stable_id(
        "equation-recognition-artifact",
        EQUATION_RECOGNITION_CONTRACT_VERSION,
        actual_request.assembly_artifact.artifact_id,
        actual_request.processor_identity.identity_digest,
        (),
        0,
        0,
        diagnostic_sha256,
    )
    return EquationRecognitionArtifact(
        artifact_id=artifact_id,
        assembly_artifact_id=actual_request.assembly_artifact.artifact_id,
        processor_identity=actual_request.processor_identity,
        proposals=(),
        invocation_exit_code=0,
        diagnostic_byte_size=0,
        diagnostic_sha256=diagnostic_sha256,
    )
