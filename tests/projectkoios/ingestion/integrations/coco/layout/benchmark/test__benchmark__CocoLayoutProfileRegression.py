"""Frozen benchmark regressions for Koios COCO Layout Profile v0.1."""

import pytest
from projectkoios.ingestion.integrations.coco.layout.detector.actionizer import (  # noqa: E501
    CocoLayoutDetectorObservationActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.detector.gate.actionizer import (  # noqa: E501
    CocoLayoutDetectorGateActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.output import (  # noqa: E501
    CocoLayoutDetectorRawOutputJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.actionizer import (  # noqa: E501
    CocoLayoutDetectorOutputParser,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.request import (  # noqa: E501
    CocoLayoutDetectorOutputParsingRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.resource import (  # noqa: E501
    CocoLayoutDetectorResource,
)
from projectkoios.ingestion.integrations.coco.layout.profile import (
    CocoLayoutProfile,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash

from tests.projectkoios.ingestion.integrations.coco.layout.detector_fixture import (  # noqa: E501
    coco_layout_detector_completed_invocation,
    coco_layout_detector_configuration,
    coco_layout_detector_raw_output,
    coco_layout_detector_request,
    coco_layout_gate_request,
    coco_layout_invocation_request,
)
from tests.projectkoios.ingestion.integrations.coco.layout.fixture import (
    coco_layout_bundle_fixture,
)

pytestmark = pytest.mark.benchmark


def test__benchmark__profile_and_category_registry_identities() -> None:
    profile = CocoLayoutProfile.koios_doclaynet_v0_1()

    assert profile.categories.inventory_id == (
        "coco-layout-category-inventory:sha256:"
        "d5df2bbf88de955f31dabe880102e245dc80924c7235461bf8eee64085ec922e"
    )
    assert profile.profile_id == (
        "coco-layout-profile:sha256:"
        "e4bcd881d980c69bf94c9ce95d98d7709707b2bb417cd513e7bc3e9f41726c33"
    )


@pytest.mark.parametrize(
    ("member_property", "expected_sha256"),
    (
        (
            "annotations_bytes",
            "0a647b196f986041dbf14128befd49e6a0b9fbb649a3c8a169c4dae64ba56b47",
        ),
        (
            "reading_order_bytes",
            "80c4b4986d902ed16f08846dfbd99d2c649d4db1321e5c2b799e078d8ac8ebbc",
        ),
        (
            "lineage_bytes",
            "6077e425011d1fc5efcf77ee48f692b2bddf0c5dd5e542f40246f618e5248d90",
        ),
        (
            "manifest_bytes",
            "5191d6f7387c29980f027d9fcaafbccd85e2844bc62d81cf79c8673609fe58b1",
        ),
    ),
)
def test__benchmark__canonical_member_digest(
    member_property: str,
    expected_sha256: str,
) -> None:
    content = getattr(coco_layout_bundle_fixture(), member_property)

    assert SHA256Fingerprinter.fingerprint(content=content) == SHA256Hash(
        expected_sha256
    )


def test__benchmark__bundle_identity() -> None:
    assert coco_layout_bundle_fixture().bundle_id == (
        "coco-layout-bundle:sha256:"
        "60c1419c33cbf45c30b7178c05258680bc1245d6e819d258cf2854cd254f21ef"
    )


def test__benchmark__heron_onnx_candidate_resource() -> None:
    resource = CocoLayoutDetectorResource.docling_heron_onnx_candidate()

    assert resource.source_revision == (
        "40bde044036bb181c130ddf6c51792187268748f"
    )
    assert resource.artifact_sha256 == SHA256Hash(
        "59c81a3a2923042d85034ffc487f8f47e4854117e879aef89b2b9f728fb4922a"
    )
    assert resource.artifact_byte_length == 171_220_471
    assert resource.resource_id == (
        "coco-layout-detector-resource:sha256:"
        "a97bbc247966fb4755f56ea7c1f72c13d63b187a9662433aca2a7a534cdce6f6"
    )


@pytest.mark.parametrize(
    ("component_name", "expected_identity"),
    (
        (
            "fixture_resource",
            "coco-layout-detector-resource:sha256:"
            "f02afccc2bf715d509a1650264b45ad501553e031569280185cf32175edab2e4",
        ),
        (
            "labels",
            "coco-layout-detector-label-mapping-inventory:sha256:"
            "5664c12ec10df118c30c82a106c5e266786efae5ab007611a4e569c800d19528",
        ),
        (
            "configuration",
            "coco-layout-detector-configuration:sha256:"
            "d4a397f29924d3378732f24c953a9a6b467f63d48907c80e3c58bc5139175519",
        ),
        (
            "request",
            "coco-layout-detector-request:sha256:"
            "0730f03b905eaf053d6a047b0457e264a94c413194b573e35b83bec1bc1d3481",
        ),
        (
            "result",
            "coco-layout-detector-result:sha256:"
            "539e48eca5bfe1cf2ead6bd43d3c8a50f419ffc8b8bbb7e1925efcc8e3ba6785",
        ),
        (
            "detections",
            "coco-layout-detection-inventory:sha256:"
            "e7d8079642dace66e8d15b35a5d6fbdeaffcadbc5b84beb89842e7aab1c577e6",
        ),
        (
            "limitations",
            "coco-layout-detector-limitation-inventory:sha256:"
            "9324bfa33949a6fe81da23424c4c8721a1e38eb84688bc199c623dea152410bb",
        ),
        (
            "preprocessing",
            "coco-layout-detector-preprocessing:sha256:"
            "d08f02485b518b088ea15ffc817d607674bd2f92a5966e07d412dd6c5b46c335",
        ),
        (
            "invocation_request",
            "coco-layout-detector-invocation-request:sha256:"
            "0be3674e5c38017820acc0d4ce541698433779fcdc37f5d3648a68d749ba7501",
        ),
        (
            "invocation_document_sha256",
            "2e33e8aef42c26ce21c27f26c3bbe38cdc1ebe644a87bc7dfdde64a5eb7d3aa8",
        ),
        (
            "gate_configuration",
            "coco-layout-detector-gate-configuration:sha256:"
            "8b997749acb8701726125c09f779baf52854bb011fd6f1dc09492e126b1b6108",
        ),
        (
            "admitted_gate_result",
            "coco-layout-detector-gate-result:sha256:"
            "92966b6914992629da96947f6c923428d31ad842c639282891b7fc9c861d2ae8",
        ),
        (
            "escalated_gate_result",
            "coco-layout-detector-gate-result:sha256:"
            "332910b5efd7dfe3778f384691fe0665ef7e18351caf7ef6cecaf575a8e60391",
        ),
        (
            "raw_output",
            "coco-layout-detector-raw-output:sha256:"
            "518c8929a09e9172f2aa963f9f33ab5a506c85cfef6c042147fa40582bc2c821",
        ),
        (
            "raw_output_sha256",
            "405383f3409725ee4ba755cf23f853f1bf092ca7e326cb0aeced14d9904fc8d4",
        ),
        (
            "output_parsing_result",
            "coco-layout-detector-output-parsing-result:sha256:"
            "c54fb44cfdbcd8ab53042100b27d5a575b715581929194728da2bf81c75b83d5",
        ),
    ),
)
def test__benchmark__detector_adapter_identity(
    component_name: str,
    expected_identity: str,
) -> None:
    configuration = coco_layout_detector_configuration()
    request = coco_layout_detector_request()
    result = CocoLayoutDetectorObservationActionizer().action(request=request)
    invocation = coco_layout_invocation_request()
    admitted_gate_request = coco_layout_gate_request()
    admitted_gate_result = CocoLayoutDetectorGateActionizer().action(
        request=admitted_gate_request
    )
    escalated_gate_result = CocoLayoutDetectorGateActionizer().action(
        request=coco_layout_gate_request(include_limitations=True)
    )
    raw_output = coco_layout_detector_raw_output()
    raw_output_bytes = (
        CocoLayoutDetectorRawOutputJsonContract().serialize_bytes(raw_output)
    )
    parsing_result = CocoLayoutDetectorOutputParser().action(
        request=CocoLayoutDetectorOutputParsingRequest(
            invocation=coco_layout_detector_completed_invocation()
        )
    )
    identities = {
        "fixture_resource": configuration.resource.resource_id,
        "labels": configuration.label_mappings.inventory_id,
        "configuration": configuration.configuration_id,
        "request": request.request_id,
        "result": result.result_id,
        "detections": result.detections.inventory_id,
        "limitations": result.limitations.inventory_id,
        "preprocessing": invocation.preprocessing.preprocessing_id,
        "invocation_request": invocation.request_id,
        "invocation_document_sha256": SHA256Fingerprinter.fingerprint(
            content=invocation.document_bytes()
        ),
        "gate_configuration": (
            admitted_gate_request.configuration.configuration_id
        ),
        "admitted_gate_result": admitted_gate_result.result_id,
        "escalated_gate_result": escalated_gate_result.result_id,
        "raw_output": raw_output.output_id,
        "raw_output_sha256": SHA256Fingerprinter.fingerprint(
            content=raw_output_bytes
        ),
        "output_parsing_result": parsing_result.result_id,
    }

    assert identities[component_name] == expected_identity
