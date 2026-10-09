# Deterministic reading-order schematic

```text
LayoutReadingOrderRequest
  |- exact render evidence
  |- upstream evidence identity and direction
  |- expected native-block inventory
  |- regions + assigned block geometry
  `- immutable candidate evidence
       |- producer request + implementation identities
       |- exact render, upstream, direction, elements
       `- candidate permutation
                 |
                 v
   coverage / membership / kind gates
                 |
                 v
 header -> pure body columns -> footer
                 |
                 v
       native-block lane ordering
                 |
                 v
 candidate exact-agreement comparison
          |                    |
          v                    v
 RESOLVED                 ESCALATION_REQUIRED
 complete region and      sorted closed reasons;
 block permutations       no partial resolution
```
