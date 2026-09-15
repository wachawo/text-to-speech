#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve the speaker-sample WAV path for engines that need voice cloning.

Kept in `libs/` (not `engines/coquitts.py`) so unit tests can import it
without pulling torch / TTS at module load time.
"""

import os
import re

from libs.exceptions import ValidationError

DEFAULT_COQUITTS_SAMPLES = "samples"
# A voice is a bare file stem: no separators, no dots, so it can never escape
# the samples directory when joined onto it. `\Z`, not `$`: `$` also matches
# before a trailing newline, which would otherwise end up in the file name.
VOICE_NAME_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,48}\Z")


def get_samples_dir() -> str:
    """Return the absolute samples directory (COQUITTS_SAMPLES, default `samples`), read at call time."""
    return os.path.abspath(os.path.expanduser(os.getenv("COQUITTS_SAMPLES", DEFAULT_COQUITTS_SAMPLES)))


def resolve_sample_path(value: str) -> str:
    """Resolve a speaker-sample value (env var / CLI flag) to an absolute path.

    A bare filename (no path separator) is searched in order:
        1. <samples dir>/<name>  (see get_samples_dir)
        2. ~/.config/<name>
    The first existing match wins. If neither exists, the samples-dir
    candidate is returned so the caller's "not found" error message
    points at a sensible location.

    Values containing a separator are expanduser'd and absolutized as-is.
    """
    if "/" in value or "\\" in value:
        return os.path.abspath(os.path.expanduser(value))
    candidates = [
        os.path.join(get_samples_dir(), value),
        os.path.expanduser(os.path.join("~/.config", value)),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


def list_sample_files() -> list[str]:
    """List the voice names (`*.wav` stems) directly inside the samples directory, sorted.

    Returns:
        Sorted list of file stems; empty when the directory does not exist.
    """
    samples_dir = get_samples_dir()
    if not os.path.isdir(samples_dir):
        return []
    names = []
    for entry in os.listdir(samples_dir):
        if entry.lower().endswith(".wav") and os.path.isfile(os.path.join(samples_dir, entry)):
            names.append(entry[: -len(".wav")])
    return sorted(names)


def sample_path_for_voice(voice: str) -> str:
    """Map a bare voice name to `<samples dir>/<voice>.wav`.

    Args:
        voice: Bare name matching VOICE_NAME_REGEX.

    Returns:
        Absolute path of the sample WAV (which may not exist yet).

    Raises:
        ValidationError: The name contains anything but [A-Za-z0-9_-] or is
            empty / longer than 48 characters (path-traversal guard).
    """
    if not isinstance(voice, str) or not VOICE_NAME_REGEX.match(voice):
        raise ValidationError(f"Invalid voice name: {voice!r} (expected ^[A-Za-z0-9_-]{{1,48}}$)")
    return os.path.join(get_samples_dir(), voice + ".wav")


def main():
    """Module entrypoint placeholder — this file is import-only."""
    pass


if __name__ == "__main__":
    main()
