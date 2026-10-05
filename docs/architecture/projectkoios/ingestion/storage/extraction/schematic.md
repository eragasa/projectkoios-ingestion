# Extraction storage schematic

```mermaid
flowchart LR
    Request["ExtractionPublicationRequest"]
    Disk["private content-addressed objects + fsynced journal"]
    Record["ExtractionPublicationEvidence<br/>record + exact payload bytes"]
    Config["ExtractionProjectionConfiguration"]
    Projector["ExtractionProjectionProjector<br/>pure and stateless"]
    ReadModel["ExtractionReadModel<br/>canonical immutable value"]
    Materializer["MongoExtractionProjectionMaterializer<br/>effectful create-once writes"]
    Mongo["MongoDB read projection"]
    Inventory["query-only inventory reader"]

    Request --> Disk
    Disk --> Record
    Record --> Projector
    Config --> Projector
    Projector --> ReadModel
    ReadModel --> Materializer
    Materializer --> Mongo
    Mongo --> Inventory
```

Disk commit precedes projection and remains authoritative. A lost or empty
MongoDB target can be rebuilt by reading bounded exact journal evidence,
projecting it without I/O, and materializing the resulting read models.

The arrows have strict names: reading obtains **source evidence**, projection is
a pure evidence-to-value transformation, materialization writes that value, and
inventory observes the resulting target. Record selection, authority, retries,
index readiness, target identity, and equivalence verification are outside the
projector.
