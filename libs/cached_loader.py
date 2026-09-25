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

import logging
import os
import threading
from collections.abc import Callable, Hashable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Models an engine with a per-request `model` keeps loaded at once (coquitts,
# kokorotts). Every id a client may name is on disk, but an xtts checkpoint is
# about 2 GB, so the number held in memory is bounded. Override with
# TTS_MODEL_CACHE_SIZE.
DEFAULT_MODEL_CACHE_SIZE = 2


def get_model_cache_size() -> int:
    """Return TTS_MODEL_CACHE_SIZE, the models one engine keeps loaded, at least 1.

    A value that is not a whole number falls back to DEFAULT_MODEL_CACHE_SIZE
    with a warning; a number below 1 counts as 1.
    """
    raw_value = os.getenv("TTS_MODEL_CACHE_SIZE", "").strip()
    if not raw_value:
        return DEFAULT_MODEL_CACHE_SIZE
    try:
        return max(1, int(raw_value))
    except ValueError:
        logger.warning(f"TTS_MODEL_CACHE_SIZE={raw_value!r} is not a number, using {DEFAULT_MODEL_CACHE_SIZE}")
        return DEFAULT_MODEL_CACHE_SIZE


def evict_oldest_entries(cache: dict, keep: int) -> None:
    """Drop the oldest entries of `cache` (insertion order) until at most `keep` remain; call under the cache lock."""
    while len(cache) > max(keep, 0):
        oldest_key = next(iter(cache))
        cache.pop(oldest_key, None)
        logger.info(f"Evicted {oldest_key!r} from the model cache")


def load_cached(cache: dict, lock: threading.Lock, key: Hashable, loader: Callable[[], T], max_entries: int | None = None) -> T:
    """Return cache[key], calling loader() once under lock to fill a miss.

    The hit path reads the dict without taking the lock: dict reads are
    atomic under the GIL, and entries are only added or removed under the
    lock. On a miss the lock is taken, the cache is checked again (another
    thread may have filled it in the meantime), and only then does loader()
    run, so concurrent first-time callers pay the load cost once and all
    receive the same object. A loader that raises leaves the key absent, so
    the next call retries, and its exception propagates unchanged.

    With `max_entries`, a miss on a full cache first drops the oldest loaded
    entries, before the load, so the old and the new model are not held
    together. A caller still using an evicted object keeps it until it is
    done; it is only no longer shared.

    Args:
        cache: Module-level dict shared by every call for one engine.
        lock: Module-level lock guarding first loads into that cache.
        key: Cache key identifying the object (model name, device, path).
        loader: Zero-argument callable that builds the object on a miss.
        max_entries: Most entries the cache holds; None keeps every entry.

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
        if max_entries is not None:
            evict_oldest_entries(cache, max_entries - 1)
        value = loader()
        cache[key] = value
        return value


def main():
    """Module entrypoint placeholder - this file is import-only."""
    pass


if __name__ == "__main__":
    main()
