# `ingestion.transcripts` implementation

The plural `transcripts` package owns the nominal document hierarchy:

- `AbstractTranscript` specializes `AbstractDocument`;
- `AbstractTranscriptPage` specializes `AbstractDocumentPage`; and
- `AbstractTranscriptBlock` specializes `AbstractDocumentBlock`.

The transcript page and block bases bridge their document-level identity and
text properties to transcript-specific properties. `CleanTranscript`,
`CleanTranscriptPage`, and `CleanTranscriptBlock` are the first concrete
implementations and preserve their established fields and stable identities.

No generic evidence base or `contracts.py` layer is introduced. The existing
singular `transcript` package continues to own operational selection and batch
namespaces during this bounded migration.
