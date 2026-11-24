# Accepted Table Evidence

## Status

Accepted-result and human-decision contract version 1.1 is a narrow,
owner-native, additive contract for accepting one exact private
table-transcription proposal by explicit human decision. It does not alter
detector output, reconstructed table structure, the proposal, or its
proofreading checklist. Proposal component contracts remain at version 1.0.

## Flow

`TableEvidenceProposalCodec` verifies the exact proposal SHA-256 and strictly
loads the current proposal schema into immutable `TableEvidenceProposal`,
`TableEvidenceParameter`, `TableEvidenceProposalRow`, and
`TableEvidenceProposalCell` values. Raw native text, normalized proposed text,
independent OCR text, cell geometry, printed headers, ordered keys, units, panel
order, and ambiguity flags remain separate.

`TableEvidenceConflictInventory` records the complete ordered set of immutable
`TableEvidenceConflictObservation` values derived from the exact checklist and
notebook cross-check. It preserves separate native-extraction, independent-OCR,
and external-notebook counts, observed text, proposed text, cell identity, and
source SHA-256.

`TableEvidenceHumanAcceptanceDecision` records the actor, verification basis,
instruction message identity and UTC timestamp, artifact UTC recording time,
proposal/checklist/notebook hashes, conflict-inventory identity, authority
boundary, and an immutable `TableEvidenceConflictDisposition` for every
inventoried conflict. Recording time cannot precede the observed instruction.

`AcceptedTableEvidenceResult.create` accepts a proposal, inventory, and decision
only when:

- row, column, and numeric-cell closure is exact;
- the decision binds the same proposal identity and SHA-256;
- every native/render or independent-OCR ambiguity has one exact observation;
- every machine-observed value matches the proposal's separately preserved raw
  native or OCR evidence;
- inventory counts match its observations;
- every inventoried machine or notebook conflict is disposed exactly once;
- each disposition matches the exact observation and selects the proposal
  value;
- every observation and disposition points to a known proposal cell; and
- accepted status and excluded-authority boundaries are explicit.

`AcceptedTableEvidenceCodec` emits canonical JSON and strictly reconstructs
only the current owner allowlist. Loading rejects unknown fields, unsupported
enums or versions, inconsistent identities, noncanonical bytes, incomplete
conflict closure, and altered values.

## Authority boundary

Accepted status means only that the recorded operator explicitly accepted the
exact table proposal as Ingestion table evidence on the stated basis. It does
not claim an independent cell-by-cell visual review. It grants no bibliographic
identity, Search admission, scientific acceptance, material validation,
publication, redistribution-rights, equation-evidence, or claim-support
authority.

Private source locations are artifact metadata, not table identities and not
redistribution permission. Consumers must continue to enforce their own owner
contracts and admission gates.
