# COCO layout integration implementation

## Boundary

`CocoLayoutRegionProposalActionizer` adapts already-frozen COCO-compatible box
detections. It does not run a detector, load model weights, acquire images, or
publish an authoritative page layout. A concrete local detector may use
Detectron2, transformers, ONNX, or another runtime without leaking vendor types
into the layout domain.

The exact input consists of:

- `LayoutPageRenderEvidence`, which binds managed image bytes and source/pixel
  mapping;
- `CocoLayoutImage`, which maps an integer COCO image ID to that exact render
  without adding a locator;
- `CocoLayoutDetectionInventory`, ordered by unique annotation ID;
- `CocoLayoutCategoryInventory`, ordered by unique category ID; and
- `CocoLayoutProposalConfiguration`, which pins profile, detector, runtime,
  model resource identity and SHA-256, category-registry identity, and the
  maximum detection count.

## Local detector observation boundary

`CocoLayoutDetectorObservationActionizer` normalizes already-frozen local
inference output. It preserves producer-declared observation order, while
assigning accepted COCO annotations contiguous IDs in canonical
`(image, category, box, score)` order. Every accepted observation retains exact
mapping and detection lineage. Unsupported labels and observations below the
configured confidence threshold remain explicit limitations rather than being
silently discarded or coerced into another category.

The first benchmark candidate is the Apache-2.0
[Docling Heron ONNX model](https://huggingface.co/docling-project/docling-layout-heron-onnx/tree/40bde044036bb181c130ddf6c51792187268748f),
pinned to repository revision `40bde044036bb181c130ddf6c51792187268748f`,
model SHA-256
`59c81a3a2923042d85034ffc487f8f47e4854117e879aef89b2b9f728fb4922a`,
and byte length `171220471`. Heron's first eleven labels map exactly to the
profile's DocLayNet registry. Its six extension labels remain unsupported
limitations in v0.1. The resource record is identity and reproducibility
evidence, not a locator, download instruction, license judgment, or execution
authorization.

The detector invocation hierarchy binds the exact canonical non-media request,
managed image reference, pinned model resource, preprocessing transformation,
runtime and execution-provider identities, device identity, output-byte bound,
elapsed nanoseconds, and exact raw output bytes. Complete and failed invocations
have closed status and failure vocabularies; request-document drift, missing
complete output, inconsistent failure fields, and oversized output fail closed.
The canonical invocation document and raw output receive independent SHA-256
digests and participate in invocation identity.

`CocoLayoutDetectorInvocationActionizer` invokes one provider exactly once; it
does not infer retries or lifecycle. `OnnxRuntimeCocoLayoutDetectorProvider` is
the concrete Heron-compatible provider. It rejects unsafe or drifting model
paths, enforces a hard model-byte ceiling before allocation, streams and
verifies exact managed image bytes under an explicit byte-provider authority,
checks decoded dimensions, validates runtime/provider/device identity, restricts
v0.1 execution to an exactly activated CPUExecutionProvider, applies the pinned
640-by-640 RGB/bilinear/uint8/NCHW preprocessing, executes the named ONNX inputs,
validates exact output tensor ranks, dimensions, dtypes, finite values, and
bounds, and serializes a typed canonical raw-output document. Managed-image and
provider-protocol failures remain inside the closed invocation failure taxonomy;
failed invocations cannot carry raw output bytes. Optional runtime dependencies
are pinned under the `layout-detector` package extra.

`CocoLayoutDetectorOutputParser` then performs strict bounded canonical parsing,
checks render/resource/preprocessing lineage, and sends the reconstructed
producer-ordered observations through
`CocoLayoutDetectorObservationActionizer`. Malformed, non-canonical, stale, or
failed invocation output remains explicit parsing evidence and never enters
proposal adaptation. Inference, parsing, observation normalization, and COCO
proposal adaptation therefore remain separate observable boundaries.

## Detector admission gate

`CocoLayoutDetectorGateActionizer` consumes a `VALID` parsing result derived
from an exact successful invocation, its reconstructed detector result, the
exact COCO proposal adaptation, and the exact deterministic native-layout
review. It rejects synthetic or mismatched evidence chains and deterministically
returns either `admitted` or `escalation_required`. Escalation reasons cover the
specific conflicts detected by the current overlap-based deterministic review,
insufficient accepted detections, configured limitation bounds, and unsupported
labels when policy makes them blocking. This review is not a complete
native/detector disagreement detector. Unsupported labels are never erased even
when policy allows them to remain nonblocking.

Admission means only that the evidence may enter a later deterministic layout
finalizer. It is not reading-order completeness, model agreement, human review,
publication eligibility, or publication authority.

## Koios COCO Layout Profile v0.1

The initial registry uses the official one-indexed DocLayNet v1 categories:
Caption, Footnote, Formula, List-item, Page-footer, Page-header, Picture,
Section-header, Table, Text, and Title. The mapping is explicit, pinned, and
included in profile and configuration identity. `Caption` maps to the dedicated
Koios caption region kind; `Formula` maps to equation; `Picture` maps to figure;
and both `Section-header` and `Title` map to title. A document claiming the Koios
profile name and version with another registry is rejected.

COCO boxes are `(x, y, width, height)` in rendered-page pixels. Every component
must be finite, origins must be non-negative, extents must be positive, and the
lossless converted `(x1, y1, x2, y2)` box must remain inside the exact render.
Profile bundles assign image IDs contiguously from one in sorted render-identity
order. Annotation IDs are contiguous from one in canonical
`(image, category, box, score)` order. Semantic duplicates, arbitrary integer-ID
assignment, unknown categories, duplicate IDs, unsorted inventories, stale image
IDs, invalid geometry, and excessive detections fail closed before adaptation or
bundle admission.

Profile v0.1 is a box-detection profile. It requires `area` to equal box width
times height, `iscrowd` to be zero, and a finite `score`. Segmentation is not
part of v0.1. Each image record retains exact render identity, media type, and
SHA-256. The COCO `file_name` is a safe deterministic bundle-local name derived
from its integer image ID and validated media type; it is not a storage locator
or authorization claim.

## Canonical bundle

A complete profile-v0.1 bundle contains exactly:

```text
manifest.json
annotations.coco.json
reading-order.json
lineage.json
```

All four members use the repository's bounded canonical JSON parser and
serializer. Malformed UTF-8, duplicate fields, non-RFC numeric constants,
trailing output, unknown or missing fields, non-canonical ordering, excessive
structures, and non-canonical replay fail closed.

`annotations.coco.json` carries COCO image, category, annotation, box, area,
crowd, and score fields plus explicit Koios profile/render/kind fields that COCO
tooling may ignore. `reading-order.json` binds complete ordered annotation-ID
and native-block-ID sequences for every image to the exact SHA-256 of
`annotations.coco.json`. `lineage.json` binds every annotation to its exact
detector record, proposal, adaptation, native-block membership, configuration,
proposal source, profile, and annotation-document SHA-256. Native-block
membership explicitly distinguishes `not_evaluated` from evaluated empty
membership.

`manifest.json` is written conceptually last. It binds the profile identity and
the exact document identity, SHA-256, byte length, media type, and fixed filename
of every other member. The manifest does not recursively hash itself.
`CocoLayoutBundle` reconstructs every member, verifies complete per-image order
and lineage coverage, re-derives proposal/adaptation identities, and compares all
manifest members with freshly serialized canonical bytes.

## Benchmark regression

The repository test framework registers the `benchmark` pytest marker. The
profile regression file under
`tests/projectkoios/ingestion/integrations/coco/layout/benchmark/` freezes the
profile identity, category-registry identity, canonical member digests, bundle
identity, pinned local-detector candidate, label map, adaptation configuration,
invocation preprocessing/request identities, canonical invocation-document
digest, and deterministic result identities. Run it independently with
`pytest -m benchmark`. Future local detector quality baselines use the same
marker but must keep private-corpus inputs and reports outside Git.

## Derivation and authority

One `CocoLayoutProposalAdaptation` binds each detection to exactly one
`LayoutRegionProposal`. The result reconstructs the proposal source and all
adaptations from the complete request; callers cannot inject an independent
proposal list. Proposal source identity includes detector, runtime, resource
hash, and full configuration identity.

The proposals remain non-authoritative evidence. They may be compared with
`PageLayoutResult` by deterministic layout review. Reading order, native-block
membership, model agreement, human review, and publication eligibility remain
Koios contracts and are deliberately absent from COCO records.

This integration is therefore suitable for token-free local detection while
preserving the existing authority boundary: normal pages can use deterministic
native layout and local detector evidence, and only explicitly unresolved cases
need bounded model escalation.
