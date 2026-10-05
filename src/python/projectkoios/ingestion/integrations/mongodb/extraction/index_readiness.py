"""MongoDB backend for extraction projection index readiness."""

from __future__ import annotations

from typing import Any

from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.backend import (  # noqa: E501
    ExtractionProjectionIndexReadinessBackend,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.backend_error import (  # noqa: E501
    ExtractionProjectionIndexReadinessBackendError,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.configuration import (  # noqa: E501
    ExtractionProjectionIndexReadinessConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.evidence import (  # noqa: E501
    ExtractionProjectionIndexReadinessEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.index import (  # noqa: E501
    ExtractionProjectionIndexDefinition,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.index_evidence import (  # noqa: E501
    ExtractionProjectionIndexEvidence,
)
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, OperationFailure, PyMongoError

MongoDocument = dict[str, Any]


class MongoExtractionProjectionIndexReadinessBackend(
    ExtractionProjectionIndexReadinessBackend
):
    """Create and observe configured extraction indexes on one target."""

    def __init__(
        self,
        *,
        database: Database[MongoDocument],
        configured_target: ExtractionProjectionTargetIdentity,
        configured_configuration: (
            ExtractionProjectionIndexReadinessConfiguration
        ),
    ) -> None:
        if type(configured_target) is not ExtractionProjectionTargetIdentity:
            raise TypeError("configured index-readiness target is invalid")
        if (
            type(configured_configuration)
            is not ExtractionProjectionIndexReadinessConfiguration
        ):
            raise TypeError(
                "configured index-readiness configuration is invalid"
            )
        if database.name != configured_target.database_name:
            raise ValueError("database and index-readiness target differ")
        if configured_target.schema_id != configured_configuration.schema_id:
            raise ValueError("index-readiness schema identities differ")
        self.database = database
        self.configured_target = configured_target
        self.configured_configuration = configured_configuration

    def ensure_index_readiness(
        self,
        *,
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionIndexReadinessConfiguration,
        authority_id: str,
    ) -> ExtractionProjectionIndexReadinessEvidence:
        """Ensure and observe every configured secondary index exactly."""
        if target != self.configured_target:
            raise ExtractionProjectionIndexReadinessBackendError(
                code="projection_target_differs",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message="index-readiness target differs",
            )
        if type(authority_id) is not str or not authority_id:
            raise ExtractionProjectionIndexReadinessBackendError(
                code="projection_index_write_authority_required",
                disposition=ExtractionActionDisposition.AUTHORITY_REQUIRED,
                message="index-readiness authority is required",
            )
        if len(authority_id) > 4_096:
            raise ExtractionProjectionIndexReadinessBackendError(
                code="projection_index_write_authority_invalid",
                disposition=ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                message="index-readiness authority is invalid",
            )
        if configuration != self.configured_configuration:
            raise ExtractionProjectionIndexReadinessBackendError(
                code="projection_index_configuration_differs",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message="index-readiness configuration differs",
            )

        observed: list[ExtractionProjectionIndexEvidence] = []
        try:
            for definition in configuration.indexes:
                collection = self.database[definition.collection_name]
                properties = collection.index_information().get(
                    definition.index_name
                )
                if properties is None:
                    collection.create_index(
                        list(definition.keys),
                        name=definition.index_name,
                        unique=definition.unique,
                    )
                    properties = collection.index_information().get(
                        definition.index_name
                    )
                if not isinstance(properties, dict):
                    raise ExtractionProjectionIndexReadinessBackendError(
                        code="projection_index_missing_after_creation",
                        disposition=(
                            ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                        ),
                        message="configured projection index is missing",
                    )
                observed.append(
                    self._index_evidence(
                        definition=definition,
                        properties=properties,
                    )
                )
        except ExtractionProjectionIndexReadinessBackendError:
            raise
        except DuplicateKeyError as error:
            raise ExtractionProjectionIndexReadinessBackendError(
                code="projection_index_creation_conflict",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message="projection index creation conflicts with stored data",
            ) from error
        except OperationFailure as error:
            if error.code == 13:
                disposition = ExtractionActionDisposition.AUTHORITY_REQUIRED
                code = "projection_index_write_not_authorized"
            elif error.code in (85, 86, 11000):
                disposition = (
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                )
                code = "projection_index_creation_conflict"
            else:
                disposition = ExtractionActionDisposition.RETRY_SAME_REQUEST
                code = "projection_index_creation_failed"
            raise ExtractionProjectionIndexReadinessBackendError(
                code=code,
                disposition=disposition,
                message="projection index creation failed",
            ) from error
        except (PyMongoError, TypeError, ValueError) as error:
            raise ExtractionProjectionIndexReadinessBackendError(
                code="projection_index_observation_failed",
                disposition=ExtractionActionDisposition.RETRY_SAME_REQUEST,
                message="projection index observation failed",
            ) from error

        return ExtractionProjectionIndexReadinessEvidence.create(
            target_id=target.target_id,
            configuration_id=configuration.configuration_id,
            authority_id=authority_id,
            schema_id=configuration.schema_id,
            indexes=tuple(observed),
        )

    @staticmethod
    def _index_evidence(
        *,
        definition: ExtractionProjectionIndexDefinition,
        properties: dict[str, Any],
    ) -> ExtractionProjectionIndexEvidence:
        keys_value = properties.get("key")
        if not isinstance(keys_value, (list, tuple)) or any(
            not isinstance(item, (list, tuple))
            or len(item) != 2
            or type(item[0]) is not str
            or not item[0]
            or type(item[1]) is not int
            or item[1] not in (-1, 1)
            for item in keys_value
        ):
            raise ExtractionProjectionIndexReadinessBackendError(
                code="projection_index_observation_invalid",
                disposition=ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                message="observed projection index keys are invalid",
            )
        keys = tuple((item[0], item[1]) for item in keys_value)
        unique = properties.get("unique", False) is True
        if keys != definition.keys or unique is not definition.unique:
            raise ExtractionProjectionIndexReadinessBackendError(
                code="projection_index_definition_differs",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message="observed projection index differs",
            )
        return ExtractionProjectionIndexEvidence.create(
            definition=definition,
            index_name=definition.index_name,
            keys=keys,
            unique=unique,
        )
