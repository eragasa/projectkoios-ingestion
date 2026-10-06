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

`base/actionizer/result.py` defines `AbstractDataObjectActionResult`, the
Ingestion-owned immutable result role for synchronous actionizers. Concrete
results inherit this owner rather than combining core result and Ingestion
immutability bases themselves.

## Structural package inventory

Compound ownership is represented by package structure, not flattened module
names. Package initializers are docstring-only ownership markers; callers import
the defining leaf directly. This slice applies the following exact path map:

| Removed module | Direct owner module |
|---|---|
| `base/data_object.py` | `base/data/object.py` |
| `base/projector/identity.py` | `base/projector/identity/model.py` |
| `base/projector/identity_error.py` | `base/projector/identity/error.py` |
| `base/projector/payload_error.py` | `base/projector/payload/error.py` |
| `base/materializer/identity.py` | `base/materializer/identity/model.py` |
| `base/materializer/identity_error.py` | `base/materializer/identity/error.py` |
| `base/inventory/identity.py` | `base/inventory/identity/model.py` |
| `base/inventory/identity_error.py` | `base/inventory/identity/error.py` |

The former modules are removed rather than retained as compatibility facades.
The moves do not change class definitions, identities, serialization, or error
inheritance.

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

### Projector terminology and failure taxonomy

The framework uses these terms narrowly and consistently:

- **source evidence** is the complete immutable input to a pure projection;
- **configuration** contains every deterministic choice not present in source
  evidence;
- **projection value** is the immutable rebuildable output;
- **projector identity** binds the implementation version and declared source,
  configuration, projection, and schema contracts;
- **materialization** is the separate effectful act of writing a projection value
  to a store; and
- **inventory** is a separate observation of already-materialized state.

`ProjectionContractError` means the fixed framework contract was violated, such
as supplying the wrong declared source, configuration, or output type.
`ProjectionPayloadError` means serialized source evidence is malformed,
noncanonical, incomplete, or structurally invalid. `ProjectionIdentityError`
means structurally valid values disagree about identity or contain duplicate
projected identities. Payload and identity errors specialize the contract error
for broad catches, but concrete code and operator evidence should retain the
most precise term. Storage and materialization failures are not projection
contract errors.

The rationale for using nominal objects as part of the LLM programming harness,
including the working hypothesis, review method, and falsification criteria, is
documented in [LLM harness design](llm-harness-design.md).
