from dataclasses import replace

import pytest
from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.equations.assembly.identity import (
    EQUATION_ASSEMBLY_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.assembly.result import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.identity import stable_id


def _result() -> EquationAssemblyResult:
    artifact_id = stable_id(
        "equation-assembly-artifact",
        EQUATION_ASSEMBLY_CONTRACT_VERSION,
        "source:fixture",
        "a" * 64,
        "document:fixture",
        "detection:fixture",
        (),
    )
    return EquationAssemblyResult(
        artifact_id=artifact_id,
        source_id="source:fixture",
        source_content_hash="a" * 64,
        document_id="document:fixture",
        detection_result_id="detection:fixture",
        assemblies=(),
    )


def test__equation_assembly_result__retains_stable_identity_namespace() -> None:
    result = _result()

    assert isinstance(result, DataObjectActionResult)
    assert isinstance(result, AbstractImmutableDataObject)
    assert result.artifact_id.startswith("equation-assembly-artifact:")
    with pytest.raises(ValueError, match="result ID is inconsistent"):
        replace(result, artifact_id="equation-assembly-artifact:invalid")
