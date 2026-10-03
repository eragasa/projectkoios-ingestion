# `pdf.extraction.geometry` implementation

`BlockGeometryRequest` retains at most five normalized coordinates plus the
backend-reported coordinate count. This bound distinguishes the valid four-value
shape from malformed overlong input without retaining an unbounded sequence.
Unavailable or non-numeric backend input is represented explicitly rather than
passed through as `object` or `Any`.

`BlockGeometryActionizer` returns a `BlockGeometry` result containing exactly
one of:

- a valid positive-area ordered `BoundingBox`; or
- no box plus one reason: `malformed`, `non_finite`,
  `negative_coordinate`, `unordered`, or `non_positive_area`.

Raw warning evidence is deterministic, non-empty, and bounded to 256 characters.
The action never swaps endpoints, clamps values, expands a degenerate box, or
uses page dimensions to invent replacement geometry.
