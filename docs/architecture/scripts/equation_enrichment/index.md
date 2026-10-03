# `scripts.equation_enrichment`

This repository module is the CLI and concrete-adapter composition boundary for
equation enrichment. The authoritative engine-neutral process belongs to
`workflow.equation_recognition`; the optional SNAKES representation belongs to
`cpn.equation_recognition`. The installable ingestion package owns neither CLI
nor workflow execution.
