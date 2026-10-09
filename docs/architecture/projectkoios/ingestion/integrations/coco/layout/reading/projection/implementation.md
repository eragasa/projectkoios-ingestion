# COCO resolved reading-order projection implementation

`CocoLayoutReadingOrderProjectionRequest` binds the exact canonical annotation
document, digest-bound lineage document, deterministic resolution result, and
one image ID. Construction verifies canonical annotation bytes against the
lineage digest, complete annotation/detection lineage, the resolver's exact
upstream identity against that lineage document, the exact render/image
binding, and a resolved rather than escalated layout result.

The actionizer maps each ordered framework-neutral proposal identity through
lineage to its canonical COCO annotation ID. It rejects missing or duplicate
proposal mappings, category or geometry drift, unevaluated native-block
membership, membership drift, duplicate block membership, and incomplete
annotation or block coverage. Its output carries the complete annotation-ID
and native-block-ID sequences required by `reading-order.json`.

This projection is deterministic evidence adaptation. It grants no publication
or Page Projection authority.
