#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for ttssrv main(): engines warm up once per serving process, and uvicorn serves the disconnect watcher."""

import uvicorn


def run_main(monkeypatch, app_module, debug: bool) -> dict:
    """Run main() with the warmup, the debug server and uvicorn replaced by recorders."""
    seen: dict = {"warmups": 0, "debug_runs": 0, "served": []}

    def warm():
        """Count a warmup instead of loading models."""
        seen["warmups"] += 1

    def debug_run(**kwargs):
        """Count a start of the debug server."""
        seen["debug_runs"] += 1

    monkeypatch.setattr(app_module, "TTS_DEBUG", debug)
    monkeypatch.setattr(app_module, "init_engine_pool", warm)
    monkeypatch.setattr(app_module.app, "run", debug_run)
    monkeypatch.setattr(uvicorn, "run", lambda asgi_app, **kwargs: seen["served"].append(asgi_app))
    assert app_module.main() == 0
    return seen


def test_debug_reloader_parent_does_not_warm_up(monkeypatch, app_module):
    """The reloader parent only watches files, so it starts the debug server without loading any model."""
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    seen = run_main(monkeypatch, app_module, debug=True)
    assert seen["debug_runs"] == 1
    assert seen["warmups"] == 0


def test_debug_reloader_child_warms_up_once(monkeypatch, app_module):
    """The reloader child is the process that serves, so it is the one that warms the engines."""
    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    seen = run_main(monkeypatch, app_module, debug=True)
    assert seen["debug_runs"] == 1
    assert seen["warmups"] == 1


def test_production_warms_up_and_serves_the_disconnect_watcher(monkeypatch, app_module):
    """Without debug there is no reloader: one warmup, and uvicorn gets the bridge wrapped by watch_disconnects."""
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    seen = run_main(monkeypatch, app_module, debug=False)
    assert seen["warmups"] == 1
    assert seen["debug_runs"] == 0
    (served,) = seen["served"]
    assert served.__qualname__ == "watch_disconnects.<locals>.wrapper"
