# `ReadingStructuredItemProducerActionizer`

Pure synchronous producer action for the current structured-transcription contract. It excludes page anchors, maps prose/heading/figure/table/equation items to the closed reading vocabulary, converts text block and visual object join keys into typed identities, derives contiguous per-page order, and returns one immutable production result. It does not infer missing items, read persistence, or construct canonical reading pages.
