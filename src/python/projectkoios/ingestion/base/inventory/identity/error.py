"""Identity-specific inventory failure."""

from projectkoios.ingestion.base.inventory.error import InventoryContractError


class InventoryIdentityError(InventoryContractError):
    """Report disagreement among inventory or provenance identities."""
