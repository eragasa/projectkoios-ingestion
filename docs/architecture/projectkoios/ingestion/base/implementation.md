# `ingestion.base` implementation

`AbstractDataObject` specializes the core `projectkoios.base.DataObject`
boundary for ingestion-owned records. `AbstractImmutableDataObject` identifies
immutable ingestion records. `AbstractIdentity` identifies immutable identity
or provenance records, `AbstractDerivation` identifies immutable records derived
from retained evidence, and `AbstractValidation` identifies immutable records
of completed contract validation.

The classes are thin ABCs with no storage or operational behavior. Concrete
implementations remain responsible for immutable representation and invariant
validation.

The rationale for using nominal objects as part of the LLM programming harness,
including the working hypothesis, review method, and falsification criteria, is
documented in [LLM harness design](llm-harness-design.md).
