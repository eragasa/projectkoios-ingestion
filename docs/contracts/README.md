# Ingestion contracts

This directory contains contract drafts, stable proposals, and accepted
contracts owned by `projectkoios-ingestion`.

| Contract ID | Authoritative document | Scope |
|---|---|---|
| `projectkoios.ingestion.clean-transcript` | [`clean-transcript-v2.md`](clean-transcript-v2.md#contract-metadata-clean-transcript) | Evidence-conservative clean-transcript artifacts |
| `projectkoios.ingestion.transcript-batch-plan` | [`clean-transcript-v2.md`](clean-transcript-v2.md#contract-metadata-transcript-batch-plan) | Reproducible transcript batch planning |
| `projectkoios.ingestion.reference-evidence` | [`reference-evidence.md`](reference-evidence.md#contract-metadata) | Source-bound extraction/transcript/audit evidence for external consumers |
| `projectkoios.ingestion.workflow-operations` | [`ingestion-workflow-operations.md`](ingestion-workflow-operations.md) | Draft ingestion-side workflow operation boundary |

The existing [`../contracts.md`](../contracts.md) remains the legacy aggregate
for implemented ingestion contracts. It is not moved by this documentation
migration because active local work extends it. Future accepted contracts may
be split into this directory through separately reviewed migrations.

Cross-repository discovery is provided by the
[Project Koios contract catalog](https://github.com/eragasa/projectkoios/blob/main/docs/contracts/README.md).
Lifecycle, pre-release versioning, compatibility, and conformance follow the
[Project Koios contract governance policy](https://github.com/eragasa/projectkoios/blob/main/docs/policies/contracts.md).
Task and recovery authority rules are defined by the
[Project Koios task and recovery policy](https://github.com/eragasa/projectkoios/blob/main/docs/policies/task-and-recovery-records.md).

The contract document itself is authoritative for status and version. This
index does not grant implementation, release, scientific, or publication
authority.
