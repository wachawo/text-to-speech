#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve the speaker-sample WAV path for engines that need voice cloning.

Kept in `libs/` (not `engines/coquitts.py`) so unit tests can import it
without pulling torch / TTS at module load time.
"""

import os


def resolve_sample_path(value: str) -> str:
    """Resolve a speaker-sample value (env var / CLI flag) to an absolute path.

    A bare filename (no path separator) is searched in order:
        1. <cwd>/samples/<name>
        2. ~/.config/<name>
    The first existing match wins. If neither exists, the cwd/samples
    candidate is returned so the caller's "not found" error message
    points at a sensible location.

    Values containing a separator are expanduser'd and absolutized as-is.
    """
    if "/" in value or "\\" in value:
        return os.path.abspath(os.path.expanduser(value))
    candidates = [
        os.path.abspath(os.path.join("samples", value)),
        os.path.expanduser(os.path.join("~/.config", value)),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


def main():
    pass


if __name__ == "__main__":
    main()
