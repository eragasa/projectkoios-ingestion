# Prototype capability inventory

The prototype demonstrated that the rewrite must support these capabilities; its names and bytes are not contracts:

- page-bound native text and selected OCR retained independently;
- explicit text selection and composition identity;
- paragraph/heading role and reading order;
- figure/table/equation evidence with source spans and labels;
- figure/table caption, legend, note, title, and subfigure-label associations;
- equation assembly/selection/recognition evidence and review/chunk gates;
- rendered PDF/PNG evidence referenced outside MongoDB;
- deterministic document/page/block identities and inventories;
- summary/completeness reconciliation from independently observed counts; and
- text-only page projection excluding unaccepted equations and non-text media.

The clean design intentionally does not preserve prototype module paths, JSONL shapes, summaries, report formats, validation IDs, or implementation policies.
