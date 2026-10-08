"""Closed logical reading-evidence storage collections."""

from enum import StrEnum


class ReadingEvidenceStorageCollection(StrEnum):
    """Identify one backend-neutral logical collection role."""

    DOCUMENTS = "documents"
    PAGES = "pages"
    BLOCKS = "blocks"
    PRODUCERS = "producers"
    REFERENCES = "references"
    LIMITATIONS = "limitations"
    COMPLETIONS = "completions"

    @classmethod
    def non_completion(
        cls,
    ) -> tuple[ReadingEvidenceStorageCollection, ...]:
        """Return exact canonical non-completion role order."""
        return tuple(value for value in cls if value is not cls.COMPLETIONS)
