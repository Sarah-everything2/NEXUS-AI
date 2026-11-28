"""Shared cross-process lock and exclusive miner coordination."""

import os
import threading
from contextlib import contextmanager
from pathlib import Path

_THREAD_LOCK = threading.RLock()
_LOCAL = threading.local()


@contextmanager
def process_lock(lock_path):
    """Serialize miner operations across threads and operating-system processes."""
    path = Path(lock_path).expanduser().resolve()

    with _THREAD_LOCK:
        depth = getattr(_LOCAL, "depth", 0)

        if depth:
            if getattr(_LOCAL, "path", None) != path:
                raise RuntimeError(
                    "Nested mining operation requested a different process lock."
                )
            _LOCAL.depth = depth + 1
            try:
                yield
            finally:
                _LOCAL.depth -= 1
            return

        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("a+b") as lock_file:
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)

            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

            _LOCAL.path = path
            _LOCAL.depth = 1

            try:
                yield
            finally:
                _LOCAL.depth = 0
                _LOCAL.path = None

                if os.name == "nt":
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def ensure_no_other_miner_running(current_engine):
    """Fail closed unless every other registered miner is positively stopped."""
    from .registry import create_default_registry

    registry = create_default_registry()

    for engine in ("cpuminer-opt", "srbminer-multi", "xmrig"):
        if engine == current_engine:
            continue

        adapter = registry.get(engine)
        if adapter is None:
            raise RuntimeError(
                f"Mining blocked: {engine} adapter is unavailable; "
                "exclusive ownership cannot be confirmed."
            )

        result = adapter.status()
        state = result.get("status") if isinstance(result, dict) else None

        if state == "STOPPED":
            continue

        if state in ("RUNNING", "UNKNOWN"):
            raise RuntimeError(
                f"Mining blocked: {engine} status is {state}; "
                "exclusive ownership cannot be confirmed."
            )

        raise RuntimeError(
            f"Mining blocked: unexpected {engine} status: {state!r}."
        )
