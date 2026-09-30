# `projectkoios.ingestion` touched-slice schematic

```mermaid
flowchart LR
    Producer["clean_transcript<br/>canonical projection"]
    Transcript["CleanTranscript"]
    Selection["transcript.evidence.selection"]
    Evidence["paired clean/raw selected evidence"]
    Downstream["downstream authoring<br/>outside ingestion"]

    Producer --> Transcript
    Transcript --> Selection
    Selection --> Evidence
    Evidence -. "explicit handoff" .-> Downstream
```

The selector consumes an in-memory canonical transcript. It introduces no
source-asset, reference, rights, search, generation, storage, API, or workflow
boundary.
