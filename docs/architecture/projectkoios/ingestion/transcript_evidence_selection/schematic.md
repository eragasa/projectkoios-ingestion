# `transcript_evidence_selection` schematic

```mermaid
flowchart LR
    Transcript["one canonical CleanTranscript"]
    IDs["bounded tuple of exact<br/>block record IDs"]
    Request["TranscriptEvidenceSelectionRequest"]
    Selector["TranscriptEvidenceSelector<br/>action → select"]
    Closed{"closed outcome"}
    Pages["SelectedTranscriptPageEvidence"]
    Blocks["SelectedTranscriptBlockEvidence<br/>clean + raw + digests"]
    Failure["no selectable evidence"]

    Transcript --> Request
    IDs --> Request
    Request --> Selector
    Selector --> Closed
    Closed -->|EVIDENCE_AVAILABLE| Pages
    Closed -->|EVIDENCE_AVAILABLE| Blocks
    Closed -->|invalid / missing / incomplete / inspect| Failure
```

All non-available outcomes expose empty page and block tuples. Page and block
evidence retain only transcript-local handoff identities and text evidence.
