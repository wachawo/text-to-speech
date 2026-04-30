#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gunicorn lifecycle hooks."""


def on_starting(server):
    """Called once in master before forking workers."""
    pass


def child_exit(server, worker):
    pass


def main():
    pass


if __name__ == "__main__":
    main()
