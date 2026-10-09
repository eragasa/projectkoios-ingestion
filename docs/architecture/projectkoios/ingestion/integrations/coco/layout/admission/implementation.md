# COCO layout region admission implementation

## Boundary

`CocoLayoutRegionAdmissionActionizer` is the generic deterministic admission
boundary for every category in one exact Koios COCO Layout Profile. It consumes
a `VALID` detector-output parsing result and the exact proposal adaptation of
that detector result. It performs no inference, retrieval, recognition,
page-layout finalization, or publication.

The request rejects mismatched render, image, detection, detector resource,
runtime, profile, and proposal evidence. Admission confidence may equal or
strengthen detector filtering but cannot weaken it.

## Independent category outcomes

The operation emits exactly one `CocoLayoutCategoryAdmission` for every profile
category, including categories with no detections. Accepted proposal adaptations
are evaluated independently within their category by:

1. admission confidence;
2. deterministic confidence-first same-category IoU suppression; and
3. a hard admitted-region count bound.

Every supported proposal receives explicit evidence with one of `admitted`,
`excluded_below_confidence`, `excluded_duplicate`, or
`escalation_required_limit`. Detector observations excluded before proposal
adaptation remain in the exact detector-limitation inventory. The combined
admission evidence and limitations therefore cover every parsed observation.

A count overflow escalates only its category and admits none of that category's
otherwise selected regions. It does not block unrelated categories. Unsupported
model labels remain explicit limitations but cannot poison supported-category
admission.

## Authority

Region admission means only that a supported proposal is eligible for its
category-specific deterministic projector. It does not establish semantic
correctness, finalize a page layout or reading order, accept recognition output,
or authorize publication. The separate full-page detector gate retains its
whole-page finalization role and is not a prerequisite for scoped region
projection.
