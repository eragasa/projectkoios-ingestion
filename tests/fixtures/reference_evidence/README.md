# Reference-evidence fixtures

These fixtures are synthetic producer records for the Proposed
`projectkoios.ingestion.reference-evidence@0.1.0` boundary.

- `complete.json` is canonical, complete, source-bound evidence containing only
  synthetic identities. It contains no source text, source filename, private
  path, machine locator, or workspace filename.
- `unsupported-generation.json` is the same sanitized shape with transcript
  artifact generation `99`. Strict parsing must reject it rather than infer
  compatibility.

The complete fixture record identity is
`reference-evidence-record:sha256:4e4ff0df36dcaace4d169050407d3f4eba64c9cdb8a47f12a30ff01ffd1d33c6`.
Fixture presence is implementation evidence only. A real references consumer
and cross-repository conformance result remain pending under
`projectkoios-references#18`; these fixtures do not accept the contract.
