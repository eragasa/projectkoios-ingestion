# `TranscriptEvidenceSelector`

Semantic `DataObjectActionizer` whose `action` method delegates directly to the
single `select` implementation path. It validates selection shape, transcript
completeness, record presence, and warning scope before producing canonically
ordered paired evidence or one explicit no-evidence outcome.

[Parent module](../index.md)
