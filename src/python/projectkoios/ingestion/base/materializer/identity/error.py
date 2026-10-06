"""Identity-specific materializer failures."""

from projectkoios.ingestion.base.materializer.error import (
    MaterializationContractError,
)


class MaterializationIdentityError(MaterializationContractError):
    """Report disagreement among implementation or target identities."""
