# `reference.page.location.projection.request`

`request.py` owns the frozen `ReferencePageLocatorProjectionRequest`. It
validates input types and a nonnegative page index. It accepts a typed,
bounded `ReferenceTopicAnchorInventory` rather than `tuple[str, ...]`.
