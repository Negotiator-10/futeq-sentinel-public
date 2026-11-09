"""One run at a time, with a lock the operating system releases when the process dies.

`DECISIONS.md` #019 decision 6 reads a `RUNNING` row in the run log two ways: if the lock is
held, another run is genuinely in progress and this one refuses; if it is not, the run that wrote
the row crashed. That reading is only sound if a crashed process cannot leave the lock behind -
otherwise "no lock" and "crashed" stop meaning the same thing, and one hard kill would block every
later run until a person deleted a file.

So the lock is not a file's existence. It is an OS-level lock on an open file - `fcntl.flock` on
Linux and macOS, `msvcrt.locking` on Windows - which the kernel drops when the holding process
exits for any reason, including being killed. The file itself stays on disk and means nothing; it
only carries the holder's pid and start time for a person to read.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

__all__ = ["RunLock", "RunInProgressError"]


class RunInProgressError(Exception):
    """Another process holds the run lock: a run is genuinely in progress, so refuse."""


class RunLock:
    """An exclusive, non-blocking, crash-released lock. Use as a context manager."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._fh = None

    @property
    def held(self) -> bool:
        """True while THIS object holds the lock."""
        return self._fh is not None

    def acquire(self) -> RunLock:
        if self._fh is not None:
            raise RunInProgressError(f"{self.path}: already held by this object")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")
        try:
            _lock(fh)
        except OSError as exc:
            fh.close()
            holder = self._holder_note()
            raise RunInProgressError(
                f"another run holds {self.path}{holder}, so a run is genuinely in progress. "
                f"Refusing rather than running two at once (#019 decision 6)."
            ) from exc
        fh.seek(0)
        fh.truncate()
        note = f"pid {os.getpid()} since {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        fh.write(note.encode("ascii"))
        fh.flush()
        self._fh = fh
        return self

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            _unlock(self._fh)
        finally:
            self._fh.close()
            self._fh = None

    def _holder_note(self) -> str:
        try:
            text = self.path.read_text(encoding="ascii").strip()
        except OSError:
            return ""
        return f" ({text})" if text else ""

    def __enter__(self) -> RunLock:
        return self.acquire()

    def __exit__(self, *exc: object) -> None:
        self.release()


if sys.platform == "win32":
    import msvcrt

    def _lock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)   # byte 0; raises OSError if held

    def _unlock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)   # raises OSError if held

    def _unlock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
