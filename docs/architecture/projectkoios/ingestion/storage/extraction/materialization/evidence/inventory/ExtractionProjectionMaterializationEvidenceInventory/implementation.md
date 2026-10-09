# `ExtractionProjectionMaterializationEvidenceInventory` implementation

The inventory requires sorted unique projection identities and a single target and configuration. It derives bounded-memory evidence and projection-identity digests plus aggregate created, unchanged, projected, and per-logical-collection counts. The completion manifest compares the projection count and identity digest with the frozen migration plan so equal counts cannot certify replay of a substituted projection set.
