# Reference-evidence fixtures

These fixtures are synthetic producer records for the Proposed
`projectkoios.ingestion.reference-evidence@0.1.0` boundary.

- `complete.json` is canonical, complete, source-bound evidence containing only
  synthetic identities. It contains no source text, source filename, private
  path, machine locator, or workspace filename.
Removed transcript generation and contract keys are exercised as strict unknown
field mutations in the parser tests; no legacy-shaped fixture is retained.

The complete fixture record identity is
`reference-evidence-record:sha256:225aad8e7e74ecdac07334c8cea431a7baf014e74722fe9c5f124ba9bce5c10a`.
Fixture presence is implementation evidence only. A real references consumer
and cross-repository conformance result remain pending under
`projectkoios-references#18`; these fixtures do not accept the contract.
