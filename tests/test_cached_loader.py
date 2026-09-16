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
from libs.cached_loader import load_cached


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
