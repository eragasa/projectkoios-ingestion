# `ReadingCleanTextProducerActionizer`

Pure synchronous producer action for the current clean-transcript contract. It binds retained clean blocks to exact selected page streams, derives contiguous per-page producer order, reconstructs replayable typed raw-to-clean transformations, and returns one immutable production result. It does not infer structured roles, execute text cleaning, read persistence, or construct canonical reading pages.
