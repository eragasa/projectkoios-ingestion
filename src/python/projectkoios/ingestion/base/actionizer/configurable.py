"""Configurable data-object actionizer boundary."""

from __future__ import annotations

from abc import ABC

from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)


class ConfigurableDataObjectActionizer[
    ConfigurationT: AbstractActionConfiguration,
    RequestT: DataObjectActionRequest,
    ResultT: DataObjectActionResult,
](DataObjectActionizer[RequestT, ResultT], ABC):
    """Add exact immutable configuration typing to an actionizer.

    Notes
    -----
    This base adds no projection or materialization semantics. Subclasses own
    their action-specific request validation and behavior while sharing one
    nominal configuration boundary.
    """

    __slots__ = ()

    configuration_type: type[ConfigurationT]

    def _require_configuration(
        self,
        *,
        request: ConfigurableDataObjectActionRequest[ConfigurationT],
    ) -> ConfigurationT:
        """Return exact typed configuration or fail the action contract.

        Parameters
        ----------
        request
            Configurable action request being validated.

        Returns
        -------
        ConfigurationT
            Exact configuration declared by the concrete actionizer.

        Raises
        ------
        TypeError
            If the request carries another configuration contract.
        """
        configuration = request.configuration
        if type(configuration) is not self.configuration_type:
            raise TypeError("action configuration contract differs")
        return configuration
