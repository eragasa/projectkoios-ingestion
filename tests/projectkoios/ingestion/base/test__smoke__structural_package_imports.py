from __future__ import annotations

from importlib import import_module

import pytest

pytestmark = pytest.mark.smoke

_IDENTITY_PACKAGES = (
    (
        "projectkoios.ingestion.base.projector.identity",
        "projectkoios.ingestion.base.projector.identity.model",
        "ProjectorIdentity",
        "projectkoios.ingestion.base.projector.identity.error",
        "ProjectionIdentityError",
        "projectkoios.ingestion.base.projector.identity_error",
    ),
    (
        "projectkoios.ingestion.base.materializer.identity",
        "projectkoios.ingestion.base.materializer.identity.model",
        "MaterializerIdentity",
        "projectkoios.ingestion.base.materializer.identity.error",
        "MaterializationIdentityError",
        "projectkoios.ingestion.base.materializer.identity_error",
    ),
    (
        "projectkoios.ingestion.base.inventory.identity",
        "projectkoios.ingestion.base.inventory.identity.model",
        "InventoryIdentity",
        "projectkoios.ingestion.base.inventory.identity.error",
        "InventoryIdentityError",
        "projectkoios.ingestion.base.inventory.identity_error",
    ),
)


@pytest.mark.parametrize(
    (
        "package_name",
        "model_module_name",
        "model_name",
        "error_module_name",
        "error_name",
        "removed_error_module_name",
    ),
    _IDENTITY_PACKAGES,
)
def test__smoke__identity_packages_use_direct_structural_imports(
    package_name: str,
    model_module_name: str,
    model_name: str,
    error_module_name: str,
    error_name: str,
    removed_error_module_name: str,
) -> None:
    package = import_module(package_name)
    model_module = import_module(model_module_name)
    error_module = import_module(error_module_name)

    assert getattr(model_module, model_name).__module__ == model_module_name
    assert getattr(error_module, error_name).__module__ == error_module_name
    assert model_name not in vars(package)
    assert error_name not in vars(package)
    with pytest.raises(ModuleNotFoundError):
        import_module(removed_error_module_name)


@pytest.mark.parametrize(
    ("package_name", "module_name", "owned_name", "removed_module_name"),
    (
        (
            "projectkoios.ingestion.base.data",
            "projectkoios.ingestion.base.data.object",
            "AbstractDataObject",
            "projectkoios.ingestion.base.data_object",
        ),
        (
            "projectkoios.ingestion.base.projector.payload",
            "projectkoios.ingestion.base.projector.payload.error",
            "ProjectionPayloadError",
            "projectkoios.ingestion.base.projector.payload_error",
        ),
    ),
)
def test__smoke__structural_packages_remove_flattened_modules(
    package_name: str,
    module_name: str,
    owned_name: str,
    removed_module_name: str,
) -> None:
    package = import_module(package_name)
    module = import_module(module_name)

    assert getattr(module, owned_name).__module__ == module_name
    assert owned_name not in vars(package)
    with pytest.raises(ModuleNotFoundError):
        import_module(removed_module_name)
