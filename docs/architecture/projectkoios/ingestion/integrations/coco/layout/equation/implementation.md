# COCO layout equation projection implementation

## Boundary

`CocoLayoutEquationProjectionActionizer` is a pure deterministic bridge from an
exact admitted `Formula` category in `CocoLayoutRegionAdmissionResult` to
equation candidate evidence. It consumes no image bytes, performs no inference
or recognition, and cannot select a LaTeX or MathML transcription.

The request binds:

- the exact generic region-admission result and its complete invocation,
  parsing, detector, proposal, limitation, and per-category lineage;
- the unique admitted profile category mapped to `LayoutRegionKind.EQUATION`;
- the exact source document, page, and `LayoutPageRenderEvidence`; and
- one bounded `CocoLayoutEquationProjectionConfiguration`.

Construction fails closed unless the formula category is independently
`admitted` and document, source, blob, page, render, mapping, category, and
annotation identities remain exact. Whole-page detector-gate admission is not a
prerequisite and grants no authority to this projector.

## Deterministic projection

The projection inspects only accepted COCO detections whose mapped category is
`Formula`. It then:

1. records detections below the equation-specific confidence threshold as
   explicit confidence exclusions;
2. orders remaining detections by descending confidence and canonical detection
   identity;
3. keeps the first detection in that order and excludes later detections whose
   intersection-over-union with an already-kept box meets the configured
   duplicate threshold;
4. transforms all four pixel-box corners through the exact affine
   `LayoutPixelMapping.pixel_box_to_source_box()` operation;
5. applies bounded source-coordinate padding clipped to the analyzed page; and
6. emits candidates in canonical `(top, left, bottom, right, detection_id)`
   order.

Every candidate binds the region-admission result, detector result, proposal result,
detection, render, mapping, pixel box, unpadded source box, padded source box,
confidence, and projection configuration. Every exclusion binds its detection,
reason, and suppressing detection where applicable. Inventories reject duplicate
or non-canonical members. The result identity includes the request, candidates,
and exclusions.

The result is candidate evidence only. It neither mutates
`PageLayoutResult` nor claims that detector geometry is a corrected or final
layout.

## Recognition-ready assembly

`CocoLayoutEquationAssembler` is the separate effectful byte boundary. For each
projected candidate it renders the candidate's padded source box through the
provided `PageRegionRenderer`, verifies exact source ID, source-blob ID, page
index, page label, coordinate system, rotation, requested region, and fresh
source-byte SHA-256, and creates a display `EquationAssemblyResult` with one
exact rendered-region artifact that retains its renderer identity.

The produced assembly is compatible with the existing equation recognition
request path. Its exact `layout_detector_without_native_text` marker permits the
Pix2Tex adapter to omit the otherwise required native-text length only when the
assembly also has one candidate, empty native text, and no native block or
source-label bindings. All remaining Pix2Tex visual-quality gates still apply.
Assembly retains the projected candidate ID as immediate input lineage and the
exact rendered artifact as evidence. It is not a recognition proposal and does
not imply semantic transcription correctness.

## Bounds and authority

Configuration limits bound confidence values, duplicate IoU, source padding,
and candidate count. Candidate overflow fails closed rather than truncating.
Formula detections excluded by confidence or overlap remain observable. Other
COCO categories remain outside this adapter rather than being recast as
equations.

The bridge requires formula-category admission, which means only eligibility
for deterministic downstream processing. It is not whole-page finalization,
human review, publication eligibility, or publication authority. Pix2Tex or
another recognizer may later
emit proposal evidence; syntax validity and MathML conversion do not establish
transcription accuracy.
