# `projectkoios.ingestion.transcript.evidence` schematic

```mermaid
flowchart LR
    Evidence["transcript evidence namespace"]
    Selection["selection package"]
    Authoring["downstream authoring"]

    Evidence --> Selection
    Selection -. "destination-independent handoff" .-> Authoring
```

Search, citation, generation, persistence, and authoring policy remain outside
this package.
