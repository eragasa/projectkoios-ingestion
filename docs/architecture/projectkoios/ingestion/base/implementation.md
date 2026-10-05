# `ingestion.base` implementation

`AbstractDataObject` specializes the core `projectkoios.base.DataObject`
boundary for ingestion-owned records. `AbstractImmutableDataObject` identifies
immutable ingestion records. `AbstractIdentity` identifies immutable identity
or provenance records, `AbstractDerivation` identifies immutable records derived
from retained evidence, and `AbstractValidation` identifies immutable records
of completed contract validation.

Each nominal class has one owner module under `projectkoios.ingestion.base`;
the package initializer is only an ownership marker. The classes are thin ABCs
with no storage or operational behavior. Concrete implementations remain
responsible for immutable representation and invariant validation.

## Projector pilot

`projectkoios.ingestion.base.projector` defines one fixed projector pattern. A
projector accepts only a canonical tuple of `AbstractProjectionSource` values
and one complete `AbstractProjectionConfiguration` through the shared
`ProjectionRequest`. It returns an `AbstractProjectionValue` through the shared
`ProjectionResult`. `ProjectorIdentity` binds its implementation, input,
configuration, output, and schema contracts.

`Projector.action()` is final. Concrete projectors implement only the pure
`project()` transformation, must be stateless, cannot declare external effects,
and cannot require authority. The framework rejects arbitrary source objects,
noncanonical or duplicate evidence, a mismatched configuration contract, and a
mismatched output contract. Materialization, inventory reads, publication,
verification, retries, and workflow state are not projector responsibilities.
This Ingestion-owned framework is a pilot; migration to the core repository
requires successful use by a concrete Ingestion projection first.

The rationale for using nominal objects as part of the LLM programming harness,
including the working hypothesis, review method, and falsification criteria, is
documented in [LLM harness design](llm-harness-design.md).
