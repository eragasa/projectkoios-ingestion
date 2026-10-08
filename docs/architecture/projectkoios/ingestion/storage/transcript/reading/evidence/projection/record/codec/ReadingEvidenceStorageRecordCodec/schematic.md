# `ReadingEvidenceStorageRecordCodec` schematic

```text
ReadingEvidenceDocument
    <-> document header
      + page members
      + block members -> producer references
      + producer/reference/limitation members
```
