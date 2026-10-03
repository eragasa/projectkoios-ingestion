# `pdf.extraction.text` implementation

`BlockTextRequest` retains immutable ordered lines of immutable span strings.
Fixed contract bounds admit at most 100,000 lines, 1,000,000 spans, and
10,000,000 source characters per block. The concrete adapter checks these
bounds while normalizing backend values, before constructing the request; the
request validates them again. Malformed backend line/span containers are
discarded, and backend dictionaries do not cross the action boundary.

`BlockTextActionizer` concatenates spans within each line, removes trailing
whitespace with the established extraction rule, omits empty resulting lines,
and joins retained lines with a single newline. `BlockText` retains the exact
request identity, composed text, actionizer identity, and action contract
version for deterministic replay.

The action does not infer reading order, normalize semantics, run OCR,
de-hyphenate, or merge evidence across source blocks.
