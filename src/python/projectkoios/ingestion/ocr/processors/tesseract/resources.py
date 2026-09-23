from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import BinaryIO

from projectkoios.ingestion.ocr.models import OCRContractLimitError
from projectkoios.ingestion.ocr.processors.tesseract.constants import (
    READ_CHUNK_BYTES,
)


class TesseractResourceManager:
    @classmethod
    def hash_bounded_file(
        cls,
        path: Path,
        maximum_bytes: int,
    ) -> tuple[str | None, int, str | None]:
        digest = hashlib.sha256()
        size = 0
        try:
            reader, declared_size = cls._open_regular_file(path)
            with reader:
                if declared_size > maximum_bytes:
                    return None, declared_size, "resource-size-limit"
                while True:
                    chunk = reader.read(READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > maximum_bytes:
                        return None, size, "resource-size-limit"
                    digest.update(chunk)
        except FileNotFoundError:
            return None, 0, "resource-missing"
        except OSError:
            return None, 0, "resource-unreadable"
        return digest.hexdigest(), size, None

    @classmethod
    def copy_bounded_file(
        cls,
        source: Path,
        destination: Path,
        maximum_bytes: int,
    ) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        reader, declared_size = cls._open_regular_file(source)
        with reader:
            if declared_size > maximum_bytes:
                raise OCRContractLimitError(
                    "language resource exceeds adapter limits"
                )
            with destination.open("xb") as writer:
                while True:
                    chunk = reader.read(READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > maximum_bytes:
                        raise OCRContractLimitError(
                            "language resource exceeds adapter limits"
                        )
                    digest.update(chunk)
                    writer.write(chunk)
                writer.flush()
                os.fsync(writer.fileno())
        return digest.hexdigest(), size

    @staticmethod
    def write_exclusive(path: Path, content: bytes) -> None:
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _open_regular_file(path: Path) -> tuple[BinaryIO, int]:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(path, flags)
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise OSError("language resource must be a regular file")
            return os.fdopen(descriptor, "rb"), int(file_stat.st_size)
        except BaseException:
            os.close(descriptor)
            raise


__all__ = ["TesseractResourceManager"]
