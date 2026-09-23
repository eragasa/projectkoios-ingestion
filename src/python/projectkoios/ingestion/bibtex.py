from __future__ import annotations

from dataclasses import dataclass


class BibtexReferenceError(ValueError):
    pass


@dataclass(frozen=True)
class BibTexRecord:
    citation_key: str
    entry_type: str
    fields: tuple[tuple[str, str], ...]


class BibtexParser:
    def parse(self, content: str, citation_key: str) -> BibTexRecord:
        from pybtex.database import parse_string  # type: ignore[import-untyped]

        bibliography = parse_string(content, bib_format="bibtex")
        try:
            entry = bibliography.entries[citation_key]
        except KeyError as error:
            raise BibtexReferenceError(
                f"BibTeX record not found: {citation_key}"
            ) from error
        return BibTexRecord(
            citation_key=citation_key,
            entry_type=str(entry.type),
            fields=tuple(
                sorted(
                    (str(name), str(value))
                    for name, value in entry.fields.items()
                )
            ),
        )


__all__ = ["BibTexRecord", "BibtexParser", "BibtexReferenceError"]
