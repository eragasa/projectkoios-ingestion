from dataclasses import replace

import pytest
from conftest import _processor, _request


def test__model_verification__rejects_observed_digest_tampering() -> None:
    request = _request()
    processor, _ = _processor(request)
    verification = processor.action(request=request).model_verification
    assert verification is not None

    with pytest.raises(ValueError, match="observed model digests"):
        replace(verification, postflight_observed_digest="b" * 64)
