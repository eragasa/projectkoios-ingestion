# `ingestion.base` implementation

`AbstractDataObject` specializes the core `projectkoios.base.DataObject`
boundary for ingestion-owned records. `AbstractImmutableDataObject` identifies
immutable ingestion records, and `AbstractIdentity` identifies immutable records
whose domain role is identity or provenance.

The classes are thin ABCs with no storage or operational behavior. Concrete
implementations remain responsible for immutable representation and invariant
validation.
