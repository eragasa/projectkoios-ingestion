# `selection.evidence` implementation

Block evidence retains transcript/page/root-block/record identities, canonical
order, clean indexed text and digest, exact raw text and digest, transformation
evidence, dehyphenation links, and the exact-pair mapping basis. Page evidence
retains aligned ordered evidence, root-block, and record-ID tuples.

```mermaid
flowchart LR
    Block["CleanTranscriptBlock"] --> Pair["exact clean/raw pair"]
    Pair --> Digests["independent SHA-256 digests"]
    Digests --> BlockEvidence["SelectedTranscriptBlockEvidence"]
    BlockEvidence --> PageEvidence["SelectedTranscriptPageEvidence"]
```

Both evidence identities bind all retained fields relevant to their handoff.
