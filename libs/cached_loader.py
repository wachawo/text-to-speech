#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Double-checked cached loading shared by the model-holding engines.

Five engines (pipertts, coquitts, silerotts, kokorotts, barktts) keep a
process-wide cache of an expensive object (an ONNX session, a torch
checkpoint, Bark's preloaded weights) and used to spell the same sequence by
hand: check the cache, take the lock, check again, load, store. Five copies
of a locking pattern are five places to get it subtly wrong, so it lives
here once, where it is audited and tested once.
"""

import threading
from collections.abc import Callable, Hashable
from typing import TypeVar

T = TypeVar("T")


def load_cached(cache: dict, lock: threading.Lock, key: Hashable, loader: Callable[[], T]) -> T:
    """Return cache[key], calling loader() once under lock to fill a miss.

    The hit path reads the dict without taking the lock: dict reads are
    atomic under the GIL and the cache is only ever appended to. On a miss
    the lock is taken, the cache is checked again (another thread may have
    filled it in the meantime), and only then does loader() run, so
    concurrent first-time callers pay the load cost once and all receive the
    same object. A loader that raises leaves the cache untouched, so the next
    call retries, and its exception propagates unchanged.

    Args:
        cache: Module-level dict shared by every call for one engine.
        lock: Module-level lock guarding first loads into that cache.
        key: Cache key identifying the object (model name, device, path).
        loader: Zero-argument callable that builds the object on a miss.

    Returns:
        The cached object for key, freshly built when it was absent.
    """
    try:
        return cache[key]
    except KeyError:
        pass
    with lock:
        if key in cache:
            return cache[key]
        value = loader()
        cache[key] = value
        return value


def main():
    """Module entrypoint placeholder - this file is import-only."""
    pass


if __name__ == "__main__":
    main()
