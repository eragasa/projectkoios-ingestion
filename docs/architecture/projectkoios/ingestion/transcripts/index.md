# `projectkoios.ingestion.transcripts`

This package owns nominal transcript document, page, and block bases.

## Contents

- `base.py` — `AbstractTranscript(AbstractDocument)`.
- `page/base.py` — `AbstractTranscriptPage(AbstractDocumentPage)`.
- `block/base.py` — `AbstractTranscriptBlock(AbstractDocumentBlock)`.

Concrete clean transcript objects implement these bases. Transcript selection
and other operations consume the document hierarchy rather than defining
parallel evidence page or block roots.
