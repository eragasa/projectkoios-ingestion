from __future__ import annotations

import os
import selectors
import shutil
import signal
import subprocess
import time
from pathlib import Path

from projectkoios.ingestion.ocr.processors.tesseract.base import (
    BaseTesseractRunner,
)
from projectkoios.ingestion.ocr.processors.tesseract.constants import (
    READ_CHUNK_BYTES,
)
from projectkoios.ingestion.ocr.processors.tesseract.models import (
    ProcessCapture,
)


class TesseractRunner(BaseTesseractRunner):
    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path | None,
        environment: dict[str, str],
        timeout_milliseconds: int,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
    ) -> ProcessCapture:
        if os.name != "posix":  # pragma: no cover
            return ProcessCapture(
                returncode=127,
                stdout=b"",
                stderr=b"POSIX subprocess isolation is unavailable",
            )
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                close_fds=True,
            )
        except OSError as error:
            return ProcessCapture(
                returncode=127,
                stdout=b"",
                stderr=str(error).encode("utf-8", errors="replace"),
            )
        if process.stdout is None or process.stderr is None:
            self._kill_process_group(process)
            process.wait()
            raise RuntimeError("subprocess capture pipes were not created")
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        limits = {"stdout": max_stdout_bytes, "stderr": max_stderr_bytes}
        exceeded = {"stdout": False, "stderr": False}
        timed_out = False
        killed = False
        deadline = time.monotonic() + timeout_milliseconds / 1_000.0
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    timed_out = True
                    self._kill_process_group(process)
                    killed = True
                    break
                events = selector.select(timeout=min(remaining, 0.05))
                for key, _ in events:
                    stream_name = str(key.data)
                    chunk = os.read(key.fd, READ_CHUNK_BYTES)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffer = buffers[stream_name]
                    limit = limits[stream_name]
                    available = max(0, limit + 1 - len(buffer))
                    if available:
                        buffer.extend(chunk[:available])
                    if len(buffer) > limit or len(chunk) > available:
                        exceeded[stream_name] = True
                        self._kill_process_group(process)
                        killed = True
                        break
                if killed:
                    break
            if killed:
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:  # pragma: no cover
                    process.kill()
                    process.wait()
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    timed_out = True
                    self._kill_process_group(process)
                    process.wait()
                else:
                    try:
                        process.wait(timeout=remaining)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        self._kill_process_group(process)
                        process.wait()
        finally:
            selector.close()
            process.stdout.close()
            process.stderr.close()
        return ProcessCapture(
            returncode=int(process.returncode),
            stdout=bytes(buffers["stdout"][:max_stdout_bytes]),
            stderr=bytes(buffers["stderr"][:max_stderr_bytes]),
            timed_out=timed_out,
            stdout_limit_exceeded=exceeded["stdout"],
            stderr_limit_exceeded=exceeded["stderr"],
        )

    @staticmethod
    def resolve_executable(value: str) -> Path | None:
        candidate: str | None
        if os.sep in value or (os.altsep is not None and os.altsep in value):
            candidate = value
        else:
            candidate = shutil.which(value)
        if candidate is None:
            return None
        path = Path(candidate).resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            return None
        return path

    @staticmethod
    def base_environment(temporary_path: Path | None) -> dict[str, str]:
        environment = {
            "LANG": "C",
            "LC_ALL": "C",
            "OMP_NUM_THREADS": "1",
            "OMP_THREAD_LIMIT": "1",
            "PATH": os.defpath,
        }
        if temporary_path is not None:
            environment["HOME"] = str(temporary_path)
            environment["TMPDIR"] = str(temporary_path)
        return environment

    @staticmethod
    def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except OSError:  # pragma: no cover
            process.kill()


__all__ = ["TesseractRunner"]
