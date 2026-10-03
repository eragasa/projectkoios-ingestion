"""Create-once equation publication inventory."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path

from projectkoios.ingestion.equations.publication.error import (
    EquationPublicationInventoryError,
)
from projectkoios.ingestion.equations.publication.status import (
    EquationPublicationInventoryStatus,
)


@dataclass(frozen=True)
class EquationPublicationInventory:
    """Safety classification of recognition/index publication files."""

    status: EquationPublicationInventoryStatus
    recognition_present: bool
    index_present: bool
    problem_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.problem_codes) != len(set(self.problem_codes)):
            raise ValueError("publication inventory problems must be unique")
        if self.status is EquationPublicationInventoryStatus.NONE:
            if (
                self.recognition_present
                or self.index_present
                or self.problem_codes
            ):
                raise ValueError("empty publication inventory is inconsistent")
        elif self.status is EquationPublicationInventoryStatus.COMPLETE_PAIR:
            if not self.recognition_present or not self.index_present:
                raise ValueError(
                    "complete publication inventory is inconsistent"
                )
            if self.problem_codes:
                raise ValueError("complete publication inventory has problems")
        elif not self.problem_codes:
            raise ValueError("partial publication inventory needs a problem")


def inspect_equation_publication_inventory(
    directory: Path,
) -> EquationPublicationInventory:
    """Classify the create-once recognition/index artifact pair."""

    entries = {
        "recognition": directory / "recognition.json",
        "index": directory / "index.json",
    }
    present: dict[str, bool] = {}
    problems: list[str] = []
    for name, path in entries.items():
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            present[name] = False
            continue
        except OSError:
            present[name] = False
            problems.append(f"{name}_uninspectable")
            continue
        present[name] = True
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            problems.append(f"{name}_unsafe")
    recognition_present = present["recognition"]
    index_present = present["index"]
    if not recognition_present and not index_present and not problems:
        status = EquationPublicationInventoryStatus.NONE
    elif recognition_present and index_present and not problems:
        status = EquationPublicationInventoryStatus.COMPLETE_PAIR
    else:
        status = EquationPublicationInventoryStatus.PARTIAL
        if (
            not recognition_present
            and "recognition_uninspectable" not in problems
        ):
            problems.append("recognition_missing")
        if not index_present and "index_uninspectable" not in problems:
            problems.append("index_missing")
    return EquationPublicationInventory(
        status=status,
        recognition_present=recognition_present,
        index_present=index_present,
        problem_codes=tuple(problems),
    )


def require_equation_publication_inventory(
    directory: Path,
) -> EquationPublicationInventory:
    """Reject partial publication while allowing complete or absent evidence."""

    inventory = inspect_equation_publication_inventory(directory)
    if inventory.status is EquationPublicationInventoryStatus.PARTIAL:
        problems = ",".join(inventory.problem_codes)
        raise EquationPublicationInventoryError(
            f"equation publication inventory is partial: {problems}"
        )
    return inventory
