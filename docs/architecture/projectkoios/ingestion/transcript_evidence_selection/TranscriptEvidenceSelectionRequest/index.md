# `TranscriptEvidenceSelectionRequest`

Immutable `DataObjectActionRequest` containing one exact `CleanTranscript` and
at most 256 selected block record IDs. It canonicalizes ID order while retaining
duplicates for explicit `INVALID_SELECTION` handling. `request_id` binds the
transcript result ID and canonical tuple.

[Parent module](../index.md)
