# `projectkoios.ingestion.integrations.coco.layout`

Framework-neutral COCO box-detection adaptation for document layout.

The package owns Koios COCO Layout Profile v0.1, COCO integer
image/category/annotation identities, `xywh` pixel geometry, a pinned DocLayNet
v1 category mapping, exact detector/runtime/model resource lineage, bounded
inventories, deterministic conversion to `LayoutRegionProposal`, and the
canonical four-member annotation/reading-order/lineage/manifest bundle. Its
local-detector boundary also owns exact runtime invocation evidence, pinned
preprocessing, strict invocation-output parsing, raw framework-neutral
observations, explicit label dispositions and exclusions, canonical
annotation-ID assignment, exact observation-to-detection lineage, a fail-closed
admission gate bound to successful invocation and valid parsing evidence, and a
strict projection from framework-neutral deterministic resolution into complete
COCO annotation/native-block sidecar sequences. The contracts record inference
without embedding a runtime or
granting publication authority.

See [implementation](implementation.md), [schematic](schematic.md), and the
[structural path map](structural-path-map.md).
