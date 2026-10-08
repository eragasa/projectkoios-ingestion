# `reference.page.location.inventory`

`inventory.py` owns immutable `ReferenceTopicAnchorInventory`,
`ReferenceTopicAnchorIdentityInventory`, and `ReferenceTopicAnchorMatch` values.
They own ordering, uniqueness, bounds, and exact match partitions so requests and
results do not expose raw string tuples as domain collections.
