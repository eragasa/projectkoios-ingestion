# Ingestion workflow operation boundary

## Contract metadata

| Field | Value |
|---|---|
| Contract ID | `projectkoios.ingestion.workflow-operations` |
| Target version | `0.1.0` |
| Status | Draft |
| Specification revision | Git commit containing this document |
| Owner | `projectkoios-ingestion` |
| Acceptance authority | Project Koios operator after ingestion, workflow, and deployment-consumer review |
| Architecture record | [`ADR20260920`][workflow-tracks-adr] |
| Task | [`INGEST-WORKFLOW-ADAPTER-01`][adapter-task] |
| Predecessor | None registered |
| Supersedes | None while draft |
| Dependencies | `projectkoios.workflow.core@0.1.0` (Proposed); `projectkoios.workflow.runtime@0.1.0` (Proposed); `projectkoios.ingestion.clean-transcript@0.1.0` (Proposed) |
| Consumers | Workflow-runtime owner and unresolved deployment-adapter owner |
| Compatibility | `unknown`; no adapter, wire, or implementation promise |
| Implementation bindings | None while draft |
| Effective baseline | None before acceptance |

## Status

Draft for ingestion-owner design and cross-repository boundary preparation.

This document does not publish a Proposed or Accepted contract. It does not
select the executable deployment-adapter repository, authorize implementation,
accept any dependency, expose a source location, run ingestion, publish an
artifact, activate a collection, release software, or grant scientific or
publication authority.

## Normative scope and conformance

The normative boundary begins at **Ownership boundary** and continues through
**Synthetic mapping vectors**, except for text explicitly marked informative.
**Promotion gates** and **Stop conditions** are also normative. Purpose,
rationale, the consumer-fit assessment, deferred decisions, and consequences
are informative.

The capitalized words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**,
**SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and
**OPTIONAL** have their meanings from the Project Koios contract-governance
policy. Lowercase uses are informative.

Candidate conformance subjects are:

- the ingestion operation planner, for effect-free request validation and plan
  construction;
- the deployment resolver, for resolving private source and artifact access
  outside workflow state;
- the ingestion worker, for invoking exact ingestion contracts;
- the immutable artifact publisher, for idempotent publication and lookup;
- the reconciliation adapter, for query-only effect resolution;
- the workflow-evidence mapper, for bounded runtime/core evidence; and
- the fixture verifier, for synthetic mapping and privacy assertions.

The executable deployment adapter is not owned by this repository. Naming a
conformance subject does not select its code owner or authorize its
implementation.

## Purpose

This boundary describes how a future deployment adapter can coordinate
`projectkoios-workflow` and `projectkoios-ingestion` without either reusable
package importing the other.

It defines ingestion-owned request, result, provenance, capability, and artifact
semantics that a deployment adapter can map to the proposed runtime planning,
execution, reconciliation, and final-evidence protocol.

## Design principles

- Workflow state carries typed identities, digests, statuses, and bounded
  references rather than document content or deployment paths.
- Ingestion contracts remain authoritative for extraction and derivation
  evidence.
- Runtime history remains authoritative for workflow attempts and effects.
- Artifact stores remain authoritative for immutable artifact payloads.
- Human decisions remain externally owned, explicit records.
- Transcript and distillation evidence remain separate.
- CPN is neither a dependency nor an authority for this boundary.

## Ownership boundary

`projectkoios-ingestion` MUST own:

- ingestion operation identities and versions;
- ingestion request/result and failure semantics;
- exact source, configuration, processor, and artifact provenance;
- artifact-generation and derivation relationships;
- ingestion capability declarations;
- mapping requirements for ingestion evidence; and
- sanitized producer-side conformance vectors.

`projectkoios-workflow` MUST own:

- workflow definitions, runs, snapshots, transition requests, and outcomes;
- runtime occurrence, reservation, claim, lease, retry, and event semantics;
- adapter planning/execution/reconciliation protocol semantics;
- runtime idempotency retention; and
- workflow audit and replay behavior.

The deployment layer MUST own:

- private source and artifact-store resolution;
- source-access and review policy;
- worker registration and execution;
- external authority verification;
- mapping between workflow and ingestion records;
- effect idempotency and reconciliation integration; and
- final adapter code location and deployment configuration.

`projectkoios-api` and `projectkoios-web` retain their interface concerns. No
repository acquires another repository's authority merely by consuming this
boundary.

## Prohibited dependencies

The ingestion package MUST NOT import workflow-core, workflow-runtime, CPN,
API, web, deployment, or private-store implementation modules.

The workflow package MUST NOT import ingestion models, processors, caches,
source resolvers, or artifact publishers.

The deployment adapter MAY import or inject both public boundaries only after
its repository owner and dependency policy are explicitly recorded. It MUST NOT
copy source bytes, transcript text, full chapter maps, credentials, or private
paths into workflow records.

## Operation catalog

The initial design uses versioned operation identities. Operation availability
is capability evidence, not authorization.

| Operation identity | Ingestion responsibility | Initial effect class |
|---|---|---|
| `ingestion.catalog-source@0.1.0` | Verify exact source and policy references | Read-only verification |
| `ingestion.extract-source@0.1.0` | Produce exact extraction and manifest evidence | Immutable publication |
| `ingestion.audit-derivation@0.1.0` | Verify lineage and publish an audit report | Immutable publication |
| `ingestion.propose-textbook-structure@0.1.0` | Produce source-bound structure proposal | Immutable publication |
| `ingestion.publish-literal-transcript@0.1.0` | Produce exact automated transcript evidence | Immutable publication |
| `ingestion.publish-chapter-projections@0.1.0` | Produce virtual chapter references | Immutable publication |
| `ingestion.publish-transcript-chunks@0.1.0` | Produce transcript-derived chunk generation | Immutable publication |
| `ingestion.propose-distillation@0.1.0` | Produce separate unreviewed distillation | Immutable publication |
| `ingestion.publish-distillation-chunks@0.1.0` | Produce distillation-derived chunks | Immutable publication |

These identities are design candidates. They MUST NOT be registered or treated
as implementation APIs until this boundary advances from Draft and exact
consumer review resolves the operation set.

Chapter-map review is not an ingestion effect. A human-owned decision reference
MAY authorize later chapter-projection work only when it binds the exact source,
structure proposal, chapter map, review policy, actor, outcome, and version.

## Common ingestion operation request

A deployment adapter MUST construct an ingestion operation request from exact,
bounded references. The request MUST contain at least:

- operation identity and contract version;
- logical subject and source-blob identities;
- source SHA-256 algorithm and digest;
- exact source byte length and media type;
- ordered upstream artifact identities and digests;
- processor, backend, configuration, and policy identities;
- expected artifact roles and contract versions;
- selection references, when the operation is bounded to pages or structure;
- hard resource and output bounds;
- runtime occurrence, attempt, plan, and effect-intent references;
- external idempotency token and declared scope identity; and
- authority and review-decision references required by policy.

The request MUST NOT contain source bytes, document text, transcript text, a
full chapter map, a credential, a private path, or a mutable GitHub object.
Private source resolution happens after authorization through an injected
deployment boundary.

## Deterministic ingestion plan

The ingestion operation planner MUST be effect-free. It MUST validate nominal
request fields, operation support, exact dependency versions, bounds, and
required references without opening the source or artifact payload.

The planner returns exactly one bounded result:

- `PLANNED`, with one immutable operation plan;
- `DISABLED`, when supplied policy or review references do not enable the
  operation; or
- `PLAN_REJECTED`, with bounded findings for malformed, unsupported, stale, or
  incomplete input.

A plan MUST bind:

- the complete operation request identity;
- operation, processor, backend, configuration, and contract versions;
- ordered input references;
- required private-resolution roles without locators;
- declared effect capability;
- deterministic derivation or cache key when available;
- expected artifact roles and evidence requirements;
- output, warning, failure, attempt, and resource bounds;
- external idempotency and reconciliation strategy; and
- mapping version for runtime and core evidence.

Planning MUST NOT read a clock, source file, artifact payload, network service,
environment secret, random source, mutable database row, or CPN marking. Facts
needed for planning MUST arrive as immutable, versioned references.

## Private resolution and worker input

After fresh dispatch authorization, the deployment resolver MAY resolve private
source bytes, artifact bytes, locators, credentials, and store handles required
for one exact effect intent.

Resolved values MUST remain process-local to the authorized worker boundary.
They MUST NOT appear in workflow requests, plans, event records, exception
messages, public logs, issue text, or result references.

The worker MUST verify that resolved source bytes match the planned source
digest, byte length, media type, and logical source identity before invoking an
ingestion processor. A mismatch MUST produce `REJECTED_BEFORE_EFFECT` evidence
and MUST NOT invoke processing or publication.

## Effect capability declaration

Every operation plan MUST declare one effect capability:

- `READ_ONLY` — no external mutation occurs;
- `CONTENT_ADDRESSED_PUT` — immutable publication is idempotent by content or
  derivation identity and supports exact lookup;
- `TOKEN_IDEMPOTENT_PUT` — publication accepts and retains the external
  idempotency token and supports token lookup;
- `NON_IDEMPOTENT_RECONCILABLE` — the effect is not safe to repeat but supports
  conclusive receipt lookup; or
- `UNSUPPORTED` — automatic execution is forbidden.

An operation MUST declare whether lookup is strongly conclusive for
`APPLIED`, `NOT_APPLIED`, and `AMBIGUOUS`. Missing capability evidence MUST map
to `UNSUPPORTED` and prevent dispatch.

The initial artifact-producing operations SHOULD require
`CONTENT_ADDRESSED_PUT` or `TOKEN_IDEMPOTENT_PUT`.

## Execution result

The ingestion worker MUST return exactly one result bound to the request, plan,
occurrence, attempt, effect intent, dispatch authorization, processor,
configuration, and external idempotency token.

Result kinds are:

- `COMPLETED`, with immutable artifact and publication-receipt references;
- `PARTIAL`, with retained immutable output, warnings, failures, and no implied
  retry;
- `FAILED_NOT_APPLIED`, with evidence proving no publication committed;
- `FAILED_APPLIED`, with exact committed evidence and failure details;
- `AMBIGUOUS`, when commit status cannot be established; or
- `REJECTED_BEFORE_EFFECT`, with evidence that processing/publication did not
  begin.

An ingestion `COMPLETED` status means only that the named processor and
publication contract completed. It MUST NOT imply human review, extraction
accuracy, scientific validity, lifecycle activation, or publication authority.

A `PARTIAL` result MUST remain truthful and inspectable. The runtime MUST NOT
automatically retry it because a second invocation could duplicate or conflict
with retained output. Owning application policy decides whether to continue,
compensate, accept bounded partial evidence, or request new work.

## Artifact publication

An immutable publication MUST use same-filesystem temporary output and atomic
commit, or an equivalent content-addressed store transaction. It MUST reject
symlinked destinations, inconsistent existing bytes, digest mismatch, identity
collision, overwrite, or incomplete manifests.

A publication receipt MUST bind:

- external idempotency token and scope;
- derivation or cache key;
- artifact identity, role, digest, byte length, and media/schema type;
- exact upstream identities;
- publisher and store contract versions;
- commit disposition such as `CREATED` or `REUSED_IDENTICAL`; and
- enough sanitized evidence for query-only reconciliation.

Temporary files and incomplete manifests are never authoritative artifacts.
Existing identical immutable output MAY be reused after exact verification.
Different output under the same identity or derivation key MUST fail closed.

## Reconciliation

The reconciliation adapter MUST query by external idempotency token,
derivation/cache key, expected artifact identity, or publication receipt. It
MUST NOT invoke the ingestion processor or repeat publication.

A reconciliation result MUST be one of:

- `CONFIRMED_APPLIED`, with exact receipt and artifact references;
- `CONFIRMED_NOT_APPLIED`, when the owning store can prove no commit;
- `CONFIRMED_PARTIAL`, with exact committed subset evidence;
- `STILL_AMBIGUOUS`; or
- `EVIDENCE_INVALID`.

A missing record is `CONFIRMED_NOT_APPLIED` only when the owning store declares
that lookup strongly consistent and complete for the exact token and scope.
Otherwise it remains `STILL_AMBIGUOUS`.

`CONFIRMED_NOT_APPLIED` MAY permit a new attempt only after runtime policy,
fresh authority verification, a new attempt-bound dispatch authorization, and
retention of all prior evidence. `CONFIRMED_APPLIED` MUST reuse the committed
result without repeating work.

## Mapping to workflow evidence

The deployment adapter MUST map ingestion results without importing ingestion
types into the workflow package.

| Ingestion evidence | Runtime/core mapping |
|---|---|
| Valid effect-free plan | Runtime operation plan and effect intent |
| `DISABLED` | Disabled adapter evidence with bounded reasons |
| `PLAN_REJECTED` | Runtime planning-rejection event; no core transition |
| `COMPLETED` | Enabled adapter evidence with generated-unreviewed artifact references |
| `PARTIAL` | Retained execution evidence and policy-owned continuation; no automatic retry |
| `FAILED_NOT_APPLIED` | Known-not-applied execution evidence |
| `FAILED_APPLIED` | Known-applied failure requiring policy or compensation |
| `AMBIGUOUS` | Reconciliation-required runtime state |
| `REJECTED_BEFORE_EFFECT` | Proven pre-effect failure evidence |
| Reconciliation result | Matching runtime reconciliation evidence |

The mapper MUST preserve exact ingestion status, warning, failure, artifact,
configuration, processor, source, and provenance identities. It MUST NOT flatten
`PARTIAL` into success, infer that an artifact is accepted, or convert technical
completion into a human decision.

## Artifact reference profile

A workflow artifact reference for ingestion output MUST contain only compact,
public-safe metadata:

- artifact identity and role;
- cryptographic digest algorithm and digest;
- byte length;
- media or schema type;
- producing contract and version;
- disposition `GENERATED_UNREVIEWED` or `OBSERVED`;
- exact source-blob identity;
- parent artifact identities; and
- owning-store reference identity without a locator.

The reference MUST NOT contain artifact bytes, excerpt text, chapter-map
content, a filename, a source locator, a private path, a credential, or a
browser URL that bypasses the API boundary.

## Human review and chapter fan-out

A structure or chapter-map proposal remains `AUTOMATED_UNREVIEWED`. A human
review decision MUST be a separate immutable reference bound to the exact
proposal, source, actor, policy, outcome, evidence, and version.

A decision accepting a chapter map means only that it MAY drive bounded
processing. It MUST NOT imply that extraction is proofread, metadata is
canonical, equations are correct, content is scientifically accepted, or
publication is authorized.

The deployment adapter MAY request bounded child workflow runs only after a
valid applicable decision. Each child MUST identify the source, accepted map,
chapter node or exact page/span projection, parent run, operation set, and
bounds. The ingestion package itself MUST NOT create workflow runs.

## Literal transcript and distillation separation

Literal transcript publication MUST preserve the exact ingestion transcript
status and provenance. Under the proposed transcript-v2 contract, its status
remains `AUTOMATED_UNREVIEWED`.

Distillation MUST use a separate contract, artifact role, identity, publication
receipt, and chunk generation. It MUST NOT replace literal transcript evidence
or serve as claim-grade citation evidence without a separately accepted
consumer policy.

A language model MAY propose distillation content only through an explicitly
identified processor. Its output MUST remain generated and unreviewed. It MUST
NOT rewrite extraction evidence, repair equations authoritatively, accept
chapters, verify citations, or grant scientific validity.

## Collection activation

Collection activation is not an ingestion operation. A deployment or WF.4
operation MAY consume ingestion-owned completeness and artifact references, but
it MUST separately own expected-pointer comparison, lifecycle authority,
pointer history, and rollback evidence.

Successful document and chapter operations MUST NOT activate a collection
automatically. This boundary neither defines nor enables activation.

## Dry run

A dry run MUST validate the public operation request, exact references,
configuration, bounds, capability declaration, expected artifact roles,
private-resolution roles, and mapping version. It MAY calculate deterministic
derivation/cache keys.

A dry run MUST NOT resolve private locators, read source or artifact payloads,
claim work, invoke ingestion processing, publish output, create a human
decision, start a child run, change a pointer, or activate a collection.

Dry-run output is a bounded proposal and MUST NOT be used as execution or
publication evidence.

## Failure and retry rules

| Condition | Effect classification | Retry rule |
|---|---|---|
| Malformed or unsupported request | Not dispatched | New corrected request only |
| Source identity mismatch | Rejected before effect | New corrected resolution only |
| Processor unavailable before work | Known not applied | Bounded retry after fresh authority |
| Publication rejected before commit | Known not applied | Bounded retry after exact verification |
| Timeout during processing/publication | Ambiguous | Reconcile first |
| Partial immutable publication | Applied or partial | Policy or compensation only |
| Exact immutable output already exists | Confirmed applied | Reuse; do not repeat |
| Output identity collision | Evidence invalid | Terminal and investigate |
| Human review absent or stale | Disabled | Obtain applicable decision |

Retry MUST use the same external effect idempotency token for one effect intent,
a new attempt identity, and a fresh attempt-bound dispatch authorization. Retry
MUST NOT erase or rewrite prior attempt evidence.

## Privacy and logging

Public contracts, workflow state, events, logs, exceptions, fixtures, and issue
records MUST exclude:

- source and artifact payloads;
- transcript, chapter-map, note, and distillation text;
- credentials and access-control material;
- filenames, private locators, and machine paths;
- private workflow payload bodies; and
- mutable database or GitHub state copied as authority.

Diagnostics MUST use bounded reason codes, counts, opaque identities, and
sanitized messages. Exact protected evidence MUST remain in its owning private
store.

## Synthetic mapping vectors

Before promotion to Proposed, sanitized vectors MUST define exact expected
planning, capability, execution, publication, reconciliation, mapping, and
prohibited-call evidence for at least:

1. valid read-only source-catalog verification;
2. deterministic extraction plan with exact source/configuration identities;
3. malformed or unsupported operation rejected before private resolution;
4. stale or mismatched source identity rejected before processing;
5. missing capability declaration preventing dispatch;
6. identical immutable artifact reused without reprocessing;
7. changed idempotency reuse failing closed;
8. timeout entering reconciliation before retry;
9. strongly conclusive lookup confirming not applied;
10. inconclusive missing lookup remaining ambiguous;
11. confirmed applied publication reused without repetition;
12. partial output retained without automatic retry;
13. failed-applied result requiring policy or compensation;
14. fresh authority and new attempt required for retry;
15. planning rejection mapping to no core transition;
16. disabled review-gated work mapping to bounded disabled evidence;
17. exact human decision enabling chapter projection only;
18. stale or wrong-subject decision failing closed;
19. bounded child-run references without chapter-map payloads;
20. literal transcript and distillation artifact separation;
21. completeness evidence that does not activate a collection;
22. symlinked destination or inconsistent existing bytes rejected;
23. privacy-safe workflow references and diagnostics; and
24. baseline mapping with no CPN dependency.

Vectors MUST use synthetic source, artifact, decision, and store identities.
They MUST NOT contain real document names, text, paths, credentials, or private
artifact metadata.

## Consumer-fit assessment

The proposed workflow runtime provides the required conceptual seams:

- structural preflight before planning;
- atomic active-occurrence reservation;
- deterministic effect-free plans;
- attempt-bound dispatch authority;
- explicit external idempotency capabilities;
- ambiguity reconciliation before retry;
- immutable execution evidence; and
- payload-free artifact references.

Ingestion already has bounded immutable request/result, warning, failure,
selection, cache, and artifact concepts. This design does not currently require
an ingestion or workflow implementation change. Exact mapping types and
serialized vectors remain deferred.

The unresolved executable adapter owner is intentional. This document provides
evidence for selecting that owner; it does not prejudge whether composition
belongs in a deployment repository, application package, or later accepted
integration package.

## Deferred decisions

Before promotion to Proposed or implementation, the owner and affected
consumers must resolve:

- final executable deployment-adapter repository and dependency policy;
- exact operation catalog and identity domains;
- serialized request, plan, result, receipt, and vector schemas;
- idempotency scope and semantic-digest field composition;
- authoritative artifact-store and receipt contracts;
- strongly conclusive lookup guarantees per operation;
- exact hard bounds and supported dependency versions;
- textbook-structure, virtual-chapter, chunk, and distillation contracts;
- activation ownership and rollback policy; and
- compatibility and migration consequences.

## Promotion gates

This Draft MUST NOT advance to Proposed until:

- the executable deployment-adapter owner and materially affected consumers are
  identified;
- the workflow-core and runtime dependencies are reviewed for this mapping;
- transcript-v2 and required ingestion artifact contracts have compatible
  target versions;
- exact operation, identity, capability, and status mappings are reviewed;
- idempotency and reconciliation capabilities are declared per operation;
- sanitized serialized vectors exist and pass strict verification;
- privacy review confirms that payloads and private paths stay outside workflow
  state; and
- no unresolved `MUST_FIX` finding remains.

Promotion to Proposed would publish a review boundary only. It would not accept
the contract or authorize implementation.

## Stop conditions

Stop before implementation if:

- the deployment adapter owner remains unresolved;
- either reusable package would import the other;
- private source resolution would enter workflow state;
- an ambiguous effect could be retried before reconciliation;
- artifact publication cannot prove idempotency or conclusive lookup behavior;
- human review, lifecycle activation, scientific validity, or publication
  authority would be inferred from technical status;
- transcript and distillation evidence would be collapsed; or
- implementation, source mutation, artifact publication, migration, release,
  or CPN promotion would begin without separate authorization.

## Consequences

- The first deployment-adapter design can be reviewed without choosing its code
  owner or importing reusable packages into each other.
- Ingestion effect capabilities become explicit inputs to runtime safety.
- Immutable publication and reconciliation evidence support no-duplicate-effect
  recovery.
- Chapter review and collection activation remain separate human decisions.
- More exact operation schemas, bounds, and sanitized fixtures are required
  before promotion or implementation.

[adapter-task]:
  https://github.com/eragasa/projectkoios-ingestion/issues/4
[workflow-tracks-adr]:
  https://github.com/eragasa/projectkoios/blob/main/docs/adr.20260920.workflow-and-cpn-development-tracks.md
