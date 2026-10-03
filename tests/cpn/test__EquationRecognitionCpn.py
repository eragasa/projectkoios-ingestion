from __future__ import annotations

import hashlib

from projectkoios.ingestion.equation_enrichment import (
    EQUATION_ENRICHMENT_CONTRACT_VERSION,
    EquationAssemblyArtifact,
    EquationRecognitionProcessorIdentity,
    EquationRecognitionResource,
)
from projectkoios.ingestion.identity import stable_id

from cpn.equation_recognition import (
    EquationRecognitionFailureToken,
    build_equation_recognition_net,
    project_equation_recognition_request,
    record_equation_recognition_failure,
)
from workflow.equation_recognition import plan_equation_recognition


def _assembly() -> EquationAssemblyArtifact:
    source_id = "source:cpn-shadow"
    source_hash = hashlib.sha256(source_id.encode()).hexdigest()
    artifact_id = stable_id(
        "equation-assembly-artifact",
        EQUATION_ENRICHMENT_CONTRACT_VERSION,
        source_id,
        source_hash,
        "document:cpn-shadow",
        "detection:cpn-shadow",
        (),
    )
    return EquationAssemblyArtifact(
        artifact_id=artifact_id,
        source_id=source_id,
        source_content_hash=source_hash,
        document_id="document:cpn-shadow",
        detection_result_id="detection:cpn-shadow",
        assemblies=(),
    )


def _processor() -> EquationRecognitionProcessorIdentity:
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
                path="/bounded/model",
                sha256="c" * 64,
                byte_size=1,
            ),
        ),
        temperature=0.01,
    )


def test__equation_recognition_cpn__shadows_workflow_request() -> None:
    assembly = _assembly()
    processor = _processor()
    expected = plan_equation_recognition(
        assembly=assembly,
        processor=processor,
    )
    net = build_equation_recognition_net(assembly, processor)

    observed = project_equation_recognition_request(net)

    assert observed == expected


def test__equation_recognition_cpn__routes_correlated_failure() -> None:
    assembly = _assembly()
    processor = _processor()
    net = build_equation_recognition_net(assembly, processor)
    request = project_equation_recognition_request(net)
    failure = EquationRecognitionFailureToken(
        request_id=request.request_id,
        message="bounded recognition failure",
    )

    assert record_equation_recognition_failure(net, failure) is failure
