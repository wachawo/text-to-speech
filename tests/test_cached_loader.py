#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs/cached_loader.py - the shared double-checked cache fill.

Pins the contract every model-holding engine relies on: one load under
concurrency, a raising loader leaves no entry behind, keys are independent,
and a hit never takes the lock.
"""

import threading
import time

import pytest

# Local imports
from libs.cached_loader import DEFAULT_MODEL_CACHE_SIZE, get_model_cache_size, load_cached


class CountingLock:
    """Context manager standing in for a lock that records each acquisition."""

    def __init__(self):
        self.acquisitions = 0
        self.inner = threading.Lock()

    def __enter__(self):
        self.acquisitions += 1
        self.inner.acquire()
        return self

    def __exit__(self, unused_type, unused_value, unused_traceback):
        self.inner.release()
        return False


def run_threads(target, count=4):
    """Start `count` threads on `target` and wait for all of them."""
    threads = [threading.Thread(target=target) for unused in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_concurrent_callers_load_once_and_share_the_object():
    """Four threads racing on an empty cache call the loader once and get one object."""
    cache: dict = {}
    lock = threading.Lock()
    calls = []
    results = []
    results_lock = threading.Lock()

    def slow_loader():
        """Record the call and sleep so concurrent callers pile up on the lock."""
        calls.append(1)
        time.sleep(0.05)
        return object()

    def call():
        """Load through the helper and keep what came back."""
        value = load_cached(cache, lock, "model", slow_loader)
        with results_lock:
            results.append(value)

    run_threads(call)
    assert len(calls) == 1
    assert len(results) == 4
    assert all(value is results[0] for value in results)
    assert cache == {"model": results[0]}


def test_raising_loader_leaves_cache_empty_and_next_call_retries():
    """A loader failure stores nothing, propagates unchanged, and the next call loads."""
    cache: dict = {}
    lock = threading.Lock()
    attempts = []

    def flaky_loader():
        """Fail on the first attempt, succeed on the second."""
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("first attempt fails")
        return "loaded"

    with pytest.raises(RuntimeError, match="first attempt fails"):
        load_cached(cache, lock, "model", flaky_loader)
    assert cache == {}
    assert load_cached(cache, lock, "model", flaky_loader) == "loaded"
    assert cache == {"model": "loaded"}
    assert len(attempts) == 2


def test_two_keys_load_independently():
    """Each key runs its own loader once and keeps its own value."""
    cache: dict = {}
    lock = threading.Lock()
    loads = []

    def loader_for(key):
        """Build a loader that records which key it served."""

        def loader():
            loads.append(key)
            return f"value-{key}"

        return loader

    assert load_cached(cache, lock, "a", loader_for("a")) == "value-a"
    assert load_cached(cache, lock, "b", loader_for("b")) == "value-b"
    assert load_cached(cache, lock, "a", loader_for("a")) == "value-a"
    assert load_cached(cache, lock, "b", loader_for("b")) == "value-b"
    assert loads == ["a", "b"]
    assert cache == {"a": "value-a", "b": "value-b"}


def test_hit_does_not_take_the_lock():
    """The first call acquires the lock to load; a hit returns without touching it."""
    cache: dict = {}
    lock = CountingLock()
    loads = []

    def loader():
        """Record the load and return a fresh object."""
        loads.append(1)
        return object()

    first = load_cached(cache, lock, "model", loader)
    assert lock.acquisitions == 1
    second = load_cached(cache, lock, "model", loader)
    assert lock.acquisitions == 1
    assert second is first
    assert len(loads) == 1


def test_max_entries_drops_the_oldest_before_loading():
    """A miss on a full cache drops the oldest entry before the load, so two models are never held over the bound."""
    cache: dict = {}
    lock = threading.Lock()
    sizes_at_load = []

    def loader_for(key):
        """Build a loader that records the cache size it saw."""

        def loader():
            sizes_at_load.append(len(cache))
            return f"value-{key}"

        return loader

    for key in ("a", "b", "c"):
        load_cached(cache, lock, key, loader_for(key), max_entries=2)
    assert list(cache) == ["b", "c"]
    assert sizes_at_load == [0, 1, 1]
    assert load_cached(cache, lock, "c", loader_for("c"), max_entries=2) == "value-c"
    assert list(cache) == ["b", "c"]


def test_max_entries_none_keeps_every_entry():
    """Without max_entries nothing is evicted, as before."""
    cache: dict = {}
    lock = threading.Lock()
    for key in range(5):
        load_cached(cache, lock, key, lambda: object())
    assert len(cache) == 5


@pytest.mark.parametrize(
    "raw_value, expected",
    [
        (None, DEFAULT_MODEL_CACHE_SIZE),
        ("", DEFAULT_MODEL_CACHE_SIZE),
        ("3", 3),
        ("0", 1),
        ("-2", 1),
        ("many", DEFAULT_MODEL_CACHE_SIZE),
    ],
)
def test_model_cache_size_reads_the_env(monkeypatch, raw_value, expected):
    """TTS_MODEL_CACHE_SIZE is a whole number of at least 1; anything else falls back to the default."""
    if raw_value is None:
        monkeypatch.delenv("TTS_MODEL_CACHE_SIZE", raising=False)
    else:
        monkeypatch.setenv("TTS_MODEL_CACHE_SIZE", raw_value)
    assert get_model_cache_size() == expected
