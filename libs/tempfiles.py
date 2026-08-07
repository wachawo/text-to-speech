#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-platform tempfile helpers — safe cleanup with retry on Windows.

On Windows, `os.unlink` immediately after a media player or subprocess released
a file can raise `PermissionError` because the OS hasn't fully released the
handle yet. `safe_unlink` retries on Windows; on Linux/macOS it does a single
attempt and warns on real permission errors.
"""

import logging
import os
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform.startswith("win")


def safe_unlink(path: str | Path, retries: int = 5, delay: float = 0.1) -> bool:
    """Delete a file, retrying on transient Windows file-locking errors.

    Args:
        path: File to remove; a missing file counts as success.
        retries: Maximum number of attempts (Windows only; other platforms
            give up after the first PermissionError).
        delay: Seconds to sleep between attempts.

    Returns:
        True if the file was deleted (or already absent), False otherwise.
        Logs a warning instead of raising — callers can ignore lingering temp
        files; the OS will reclaim them.
    """
    p = os.fspath(path)
    if not os.path.exists(p):
        return True

    last_exc: Exception | None = None
    for unused_attempt in range(retries):
        try:
            os.unlink(p)
            return True
        except FileNotFoundError:
            return True
        except PermissionError as exc:
            last_exc = exc
            if not IS_WINDOWS:
                logger.warning(f"Cannot delete {p}: {type(exc).__name__}: {exc}")
                return False
            time.sleep(delay)
        except OSError as exc:
            last_exc = exc
            time.sleep(delay)

    logger.warning(f"Failed to delete {p} after {retries} attempts: {type(last_exc).__name__}: {last_exc}")
    return False


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
