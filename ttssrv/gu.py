#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gunicorn lifecycle hooks for the ttssrv Flask application."""


def on_starting(server):
    """Run once in the master process before workers are forked.

    Args:
        server: Gunicorn ``Arbiter`` instance owning the worker pool.
    """
    pass


def child_exit(server, worker):
    """Run in the master process after a worker has exited.

    Args:
        server: Gunicorn ``Arbiter`` instance owning the worker pool.
        worker: The worker object that just terminated.
    """
    pass


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
