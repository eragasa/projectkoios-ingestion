# Deterministic reading-order implementation

## Contract

`LayoutReadingOrderRequest` binds exact `LayoutPageRenderEvidence`, an upstream
evidence identity, configured direction, complete expected
native-block inventory, semantic regions, native-block membership and geometry,
and immutable `LayoutReadingOrderCandidateEvidence`. Candidate evidence retains
the producer request and implementation identities, exact render and upstream
bindings, direction, ordered element IDs/kinds/boxes, and candidate permutation.
The request rejects candidate metadata or element evidence that differs from its
resolver inputs. Derived identities include every bound value and configuration.

A successful `LayoutReadingOrderResult` contains duplicate-free complete
semantic-region and native-block sequences. An escalation contains no partial
resolution and at least one sorted closed reason. Result construction re-runs
the pure derivation and rejects forged status, reasons, or permutations.

## Mechanical rules

The verifier:

1. validates candidate coverage and rejects unknown candidate regions;
2. validates every expected native block is assigned exactly once and rejects
   unknown blocks or blocks outside their assigned region;
3. rejects unsupported `sidebar` and `other` regions;
4. escalates captions and footnotes because this contract has no exact
   association evidence for them;
5. rejects positive-area region overlap and conflicting header/footer placement;
6. places valid headers first and valid footers last;
7. admits only a consecutive leading title prefix, where each promoted title is
   wholly above and horizontally spans every remaining region, including any
   not-yet-promoted title;
8. partitions remaining body regions by transitive horizontal overlap;
9. admits only columns with a common positive horizontal lane, vertically
   non-overlapping members, and direct positive vertical-overlap evidence
   between every pair of columns;
10. orders columns by configured left-to-right or right-to-left direction;
11. admits native blocks only when each region contains one vertically coherent
    lane; and
12. requires exact candidate agreement with the derived complete region order.

A spanning region inside the body connects otherwise separate columns without a
common lane and escalates. Geometry conflicts, source-order-sensitive
disagreement, and incomplete mappings are never resolved by tie-breaking.

## Authority boundary

The result is deterministic resolution evidence only. It does not rewrite the
baseline, authorize Page Projection or Search chunking, establish ground truth,
or grant publication eligibility.
