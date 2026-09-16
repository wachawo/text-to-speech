#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In-process synthesis metrics for ttssrv: per-engine counters and latencies, plus the Prometheus text view."""

import math
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from datetime import datetime

# Latencies kept per engine for the percentiles; the counters and the sum cover every call.
LATENCY_WINDOW = 1000
# (percentile, snapshot key, Prometheus quantile label)
QUANTILES = ((50, "p50_ms", "0.5"), (95, "p95_ms", "0.95"), (99, "p99_ms", "0.99"))
PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def percentile(values: Iterable[int], p: float) -> int | None:
    """Nearest-rank percentile (0 < p <= 100) over a sorted copy, None when there are no values."""
    ordered = sorted(values)
    if not ordered:
        return None
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def new_engine_stats() -> dict:
    """Return the zeroed per-engine record the registry keeps."""
    return {
        "calls": 0,
        "failures": 0,
        "sum_ms": 0,
        "last_error": None,
        "last_error_at": None,
        "latencies": deque(maxlen=LATENCY_WINDOW),
        "warm": False,
    }


def format_time(epoch: float | None) -> str | None:
    """Local ISO 8601 time with milliseconds, the same shape the JSON log uses; None stays None."""
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch).isoformat(timespec="milliseconds")


def engine_snapshot(stats: dict, available: bool) -> dict:
    """Build the read-only view of one engine's record."""
    latencies = list(stats["latencies"])
    calls = stats["calls"]
    view = {
        "calls": calls,
        "failures": stats["failures"],
        "last_error": stats["last_error"],
        "last_error_at": format_time(stats["last_error_at"]),
    }
    for p, key, unused_label in QUANTILES:
        view[key] = percentile(latencies, p)
    view["avg_ms"] = round(stats["sum_ms"] / calls) if calls else None
    view["sum_ms"] = stats["sum_ms"]
    view["available"] = available
    view["warm"] = stats["warm"]
    return view


# The registry: one process-wide store, guarded by LOCK. Every writer below
# takes the lock; readers copy what they need under it and build the view outside.
LOCK = threading.Lock()
STARTED = time.monotonic()
WAITING = 0
ENGINES: dict[str, dict] = {}


def stats_for(engine: str) -> dict:
    """Return the record of an engine, creating it; the caller holds LOCK."""
    return ENGINES.setdefault(engine, new_engine_stats())


def record(engine: str, ms: int, ok: bool, error: str | None = None) -> None:
    """Count one synthesis call with its latency; a failure also keeps the error name and time."""
    with LOCK:
        stats = stats_for(engine)
        stats["calls"] += 1
        stats["sum_ms"] += ms
        stats["latencies"].append(ms)
        if not ok:
            stats["failures"] += 1
            stats["last_error"] = error
            stats["last_error_at"] = time.time()


def set_warm(engine: str, warm: bool) -> None:
    """Store the warmup outcome of a preloaded engine."""
    with LOCK:
        stats_for(engine)["warm"] = warm


def wait_begin() -> None:
    """Count one more request waiting for a pool slot."""
    global WAITING
    with LOCK:
        WAITING += 1


def wait_end() -> None:
    """Count one request that stopped waiting for a pool slot."""
    global WAITING
    with LOCK:
        WAITING -= 1


def reset() -> None:
    """Drop every record and the waiting counter, and restart the uptime clock (tests)."""
    global WAITING, STARTED
    with LOCK:
        ENGINES.clear()
        WAITING = 0
        STARTED = time.monotonic()


def snapshot(pool_size: int, pool_available: int, queue_size: int, available: Iterable[str]) -> dict:
    """Return a plain dict with uptime, the pool numbers and one entry per engine seen."""
    installed = set(available)
    with LOCK:
        engines = {name: engine_snapshot(stats, name in installed) for name, stats in sorted(ENGINES.items())}
        waiting = WAITING
        uptime = int(time.monotonic() - STARTED)
    return {
        "uptime_s": uptime,
        "pool": {"size": pool_size, "available": pool_available, "queue_size": queue_size, "waiting": waiting},
        "engines": engines,
    }


def escape_label(value: str) -> str:
    """Escape a label value the way the exposition format requires: backslash, quote, newline."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def total_samples(name: str, engine: str, stats: dict) -> list[str]:
    """Counter samples of one engine: calls that succeeded and calls that failed."""
    return [
        f'{name}{{engine="{engine}",result="ok"}} {stats["calls"] - stats["failures"]}',
        f'{name}{{engine="{engine}",result="failed"}} {stats["failures"]}',
    ]


def latency_samples(name: str, engine: str, stats: dict) -> list[str]:
    """Summary samples of one engine: the quantiles it has, then _sum and _count."""
    lines = [
        f'{name}{{engine="{engine}",quantile="{label}"}} {stats[key]}'
        for unused_p, key, label in QUANTILES
        if stats[key] is not None
    ]
    lines.append(f'{name}_sum{{engine="{engine}"}} {stats["sum_ms"]}')
    lines.append(f'{name}_count{{engine="{engine}"}} {stats["calls"]}')
    return lines


def flag_samples(field: str) -> Callable[[str, str, dict], list[str]]:
    """Return a sampler that emits one boolean field of the engine record as 0/1."""

    def sample(name: str, engine: str, stats: dict) -> list[str]:
        """Gauge sample of one engine for the captured field."""
        return [f'{name}{{engine="{engine}"}} {int(bool(stats[field]))}']

    return sample


def family(name: str, kind: str, help_text: str, sampler: Callable[[str, str, dict], list[str]], engines: dict) -> list[str]:
    """HELP and TYPE lines of one metric family followed by its samples for every engine."""
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} {kind}"]
    for engine, stats in engines.items():
        lines.extend(sampler(name, escape_label(engine), stats))
    return lines


def prometheus_text(snapshot: dict) -> str:
    """Render a snapshot() dict in the Prometheus exposition format (text/plain; version=0.0.4)."""
    pool = snapshot["pool"]
    engines = snapshot["engines"]
    lines = [
        "# HELP tts_uptime_seconds Seconds since the server started.",
        "# TYPE tts_uptime_seconds gauge",
        f"tts_uptime_seconds {snapshot['uptime_s']}",
        "# HELP tts_pool_slots Engine pool slots, in total and free right now.",
        "# TYPE tts_pool_slots gauge",
        f'tts_pool_slots{{state="size"}} {pool["size"]}',
        f'tts_pool_slots{{state="available"}} {pool["available"]}',
        "# HELP tts_queue_waiting Requests waiting for a free pool slot.",
        "# TYPE tts_queue_waiting gauge",
        f"tts_queue_waiting {pool['waiting']}",
        "# HELP tts_queue_size Requests allowed to wait for a slot before a 503.",
        "# TYPE tts_queue_size gauge",
        f"tts_queue_size {pool['queue_size']}",
    ]
    lines += family("tts_synthesis_total", "counter", "Synthesis calls per engine and result.", total_samples, engines)
    lines += family("tts_synthesis_latency_ms", "summary", "Engine call time in milliseconds.", latency_samples, engines)
    lines += family("tts_engine_available", "gauge", "1 when the engine is installed.", flag_samples("available"), engines)
    lines += family(
        "tts_engine_warm", "gauge", "1 when the engine was preloaded and its warmup succeeded.", flag_samples("warm"), engines
    )
    return "\n".join(lines) + "\n"


def main():
    pass


if __name__ == "__main__":
    main()
