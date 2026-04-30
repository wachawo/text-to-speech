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
from typing import Optional, Union

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform.startswith("win")


def safe_unlink(path: Union[str, Path], retries: int = 5, delay: float = 0.1) -> bool:
    """Delete a file, retrying on transient Windows file-locking errors.

    Returns True if the file was deleted (or already absent), False otherwise.
    Logs a warning instead of raising — caller can ignore lingering temp files;
    the OS will reclaim them.
    """
    p = os.fspath(path)
    if not os.path.exists(p):
        return True

    last_exc: Optional[Exception] = None
    for _ in range(retries):
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

    logger.warning(
        f"Failed to delete {p} after {retries} attempts: "
        f"{type(last_exc).__name__}: {last_exc}"
    )
    return False


def main():
    pass


if __name__ == "__main__":
    main()
