# MongoDB reading-evidence implementation

## Ownership

This provider owns current-schema operational materialization, source reconstruction, inventories, and schema migration for `ReadingEvidenceDocument`. It does not own canonical semantics, large payload bytes, source extraction, retries, cutover approval, or Workflow lifecycle.

## Current-schema materialization

`MongoReadingEvidenceMaterializer` accepts one bounded `MongoReadingEvidenceMaterializationRequest` containing a complete successful canonical projection, explicit target generation, schema version, configuration, and authority identity. It writes immutable generation-scoped documents, pages, blocks/evidence, lineage, limitations, and managed references in dependency order.

Writes use bounded create-once batches and idempotent exact replay. Existing records are unchanged only when the complete canonical record matches; any conflict fails closed. There is no generation-wide transaction and no mutable staged manifest.

After all child records exist, the materializer reconstructs the generation through the same strict source decoder, independently recomputes its canonical inventory and identity, compares it with the projection result, and creates one immutable `MongoReadingEvidenceCompletionManifest` last. Partial generations have no completion manifest and are invisible to normal readers. Workflow owns retry and orphan cleanup.

## Source retrieval

`MongoReadingEvidenceSourceActionizer` accepts exact document/projection/generation expectations and requires one current-schema completion manifest. It performs bounded reads, rejects missing/extra/duplicate/conflicting records, reconstructs typed canonical values, recomputes identities/inventories, verifies the manifest, and returns `ReadingEvidenceSourceResult`.

Core source code decodes only the current schema. It never branches on historical schema versions.

## Inventory

`MongoReadingEvidenceInventoryObserver` reports completed and incomplete generations separately, exact counts/digests/schema versions, and completion-manifest coverage without changing state. Operational consumers select only current-schema completed generations.

## Schema migration

Database evolution is explicit and side-by-side:

1. freeze an exact source inventory;
2. create a `MongoReadingEvidenceMigrationPlan` of contiguous adjacent typed schema steps resolved through `MongoReadingEvidenceMigrationStepRegistry`;
3. migrate one bounded identity/page batch per action request into a new target generation;
4. inventory source and target independently;
5. produce `MongoReadingEvidenceMigrationVerificationResult` from canonical domain equivalence plus declared intentional schema differences;
6. use `MongoReadingEvidenceMigrationCompletionActionizer` to re-observe the target and publish the immutable completion manifest; and
7. let Workflow perform separately authorized reader cutover.

Migration never mutates source records in place, never asks core readers to decode old schemas, and never deletes source collections during cutover. Normal sources are immutable completed generations. A mutable prototype source requires a Workflow-owned write-freeze barrier; final verification re-observes the source inventory and fails on any drift before completion publication. Reader cutover is an explicit deployment configuration change referencing the target completion manifest. Rollback selects the prior completed generation/schema. Production migration and destructive cleanup require separate authorization.

The prototype JSONL/report formats are not database schemas and receive no runtime decoder. If prototype-derived data already exists in MongoDB, the first migration step treats that database layout as an explicit source schema and produces only current canonical target records.
