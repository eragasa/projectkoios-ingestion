# `ingestion.page_projection` schematic

```text
explicit document metadata + source PDF + composed baseline
                         |
reading transcript + summary + private PNG evidence
                         |
                         v
              validate_page_projection
                         |
        +----------------+----------------+
        |                                 |
        v                                 v
path-free validation report     immutable text + caption pages
        |                                 |
        +----------------+----------------+
                         |
                         v
       load_owner_validated_page_projection
                         |
                         v
       downstream explicit admission plan
```

Equation evidence, proposals, media paths, and media bytes stop at owner
validation and are not members of the downstream page types. Owner-validated
caption text remains available exactly once without its media path.
