#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generation history store: a directory of audio files with JSON sidecars, no database.

Every item is `<id>.<wav|mp3|bin>` plus `<id>.json` under the history directory.
The id is `<YYYYmmdd_HHMMSS>_<6 hex>`, so ids sort chronologically as strings and
are safe to use as file names. Every function that takes an id validates it with
`is_valid_id()` before touching the filesystem.
"""

import io
import json
import logging
import os
import re
import traceback
import uuid
import wave
from datetime import datetime

# Local imports
# Re-exported on purpose: ttssrv.app1 and the tests still reach the sniffer as
# history.is_mp3 / history.audio_format.
from libs.audio import audio_format, is_mp3  # noqa: F401

logger = logging.getLogger(__name__)

ITEM_ID_RE = re.compile(r"^\d{8}_\d{6}_[0-9a-f]{6}$")
CREATED_AT_FMT = "%Y-%m-%d %H:%M:%S"
ID_TIME_FMT = "%Y%m%d_%H%M%S"


def is_valid_id(item_id: str) -> bool:
    """Return True when `item_id` matches the history id pattern."""
    return isinstance(item_id, str) and ITEM_ID_RE.fullmatch(item_id) is not None


def new_item_id(now: datetime) -> str:
    """Build a fresh id: the timestamp of `now` plus six random hex characters."""
    return f"{now.strftime(ID_TIME_FMT)}_{uuid.uuid4().hex[:6]}"


def audio_seconds(audio_bytes: bytes, fmt: str) -> float | None:
    """Return the WAV duration in seconds (2 decimals); None for other formats or a bad header."""
    if fmt != "wav":
        return None
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            framerate = wav_file.getframerate()
            if framerate <= 0:
                return None
            return round(wav_file.getnframes() / framerate, 2)
    except (wave.Error, EOFError, ValueError) as exc:
        logger.warning(f"Cannot read WAV header: {type(exc).__name__}: {exc}")
        return None


def path_within(history_dir: str, filename: str) -> str:
    """Join `filename` onto the history directory, refusing anything that resolves outside it.

    The id regex already admits no separators; this is the second fence.
    """
    base = os.path.realpath(history_dir)
    target = os.path.realpath(os.path.join(base, filename))
    if os.path.dirname(target) != base:
        raise ValueError(f"Path escapes the history directory: {filename!r}")
    return target


def json_path(history_dir: str, item_id: str) -> str:
    """Return the sidecar path for `item_id` (callers check the id first)."""
    return path_within(history_dir, f"{item_id}.json")


def write_atomic(path: str, data: bytes) -> None:
    """Write `data` to `path` through a `.tmp` neighbour and `os.replace`."""
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "wb") as handle:
        handle.write(data)
    os.replace(tmp_path, path)


def save_item(history_dir: str, audio_bytes: bytes, meta: dict, now: datetime, max_items: int) -> dict:
    """Store audio plus its JSON sidecar and prune the directory; return the item."""
    os.makedirs(history_dir, exist_ok=True)
    item_id = new_item_id(now)
    fmt = audio_format(audio_bytes)
    text = meta.get("text") or ""
    item = {
        "id": item_id,
        "created_at": now.strftime(CREATED_AT_FMT),
        "engine": meta.get("engine"),
        "language": meta.get("language"),
        "voice": meta.get("voice"),
        "format": fmt,
        "bytes": len(audio_bytes),
        "seconds": audio_seconds(audio_bytes, fmt),
        "text": text,
        "text_chars": len(text),
        "elapsed": round(float(meta.get("elapsed") or 0.0), 2),
    }
    # Audio first, then the sidecar: a crash in between never leaves a json without audio.
    write_atomic(path_within(history_dir, f"{item_id}.{fmt}"), audio_bytes)
    write_atomic(json_path(history_dir, item_id), json.dumps(item, ensure_ascii=False).encode("utf-8"))
    logger.info(f"History item {item_id} saved ({fmt}, {len(audio_bytes)} bytes)")
    prune(history_dir, max_items)
    return item


def read_item(history_dir: str, item_id: str) -> dict | None:
    """Load the sidecar for `item_id`; None when missing or unreadable (with a warning)."""
    path = json_path(history_dir, item_id)
    try:
        with open(path, encoding="utf-8") as handle:
            item = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning(f"Skipping unreadable history item {path}: {type(exc).__name__}: {exc}")
        return None
    if not isinstance(item, dict):
        logger.warning(f"Skipping history item {path}: sidecar is not a JSON object")
        return None
    return item


def list_ids(history_dir: str) -> list[str]:
    """Return every valid item id that has a sidecar, newest first."""
    try:
        names = os.listdir(history_dir)
    except FileNotFoundError:
        return []
    ids = [name[:-5] for name in names if name.endswith(".json") and is_valid_id(name[:-5])]
    return sorted(ids, reverse=True)


def cut_text(text: str, limit: int) -> str:
    """Shorten `text` to `limit` characters, appending "..." when something was cut."""
    if limit < 0 or len(text) <= limit:
        return text
    return text[:limit] + "..."


def list_items(history_dir: str, limit: int, offset: int, text_preview: int = 200) -> tuple[int, list[dict]]:
    """Return (total, page) of items newest first, with `text` cut to `text_preview` characters."""
    ids = list_ids(history_dir)
    page = []
    for item_id in ids[offset : offset + limit]:
        item = read_item(history_dir, item_id)
        if item is None:
            continue
        item["text"] = cut_text(item.get("text") or "", text_preview)
        page.append(item)
    return len(ids), page


def get_item(history_dir: str, item_id: str) -> dict | None:
    """Return the full item (untruncated text) or None when the id is invalid or unknown."""
    if not is_valid_id(item_id):
        return None
    return read_item(history_dir, item_id)


def audio_path(history_dir: str, item_id: str) -> str | None:
    """Return the path of the existing audio file for `item_id`, or None."""
    if not is_valid_id(item_id):
        return None
    item = read_item(history_dir, item_id)
    if item is None:
        return None
    fmt = item.get("format")
    if not isinstance(fmt, str) or not re.fullmatch(r"[a-z0-9]{1,8}", fmt):
        logger.warning(f"History item {item_id} has an invalid format: {fmt!r}")
        return None
    path = path_within(history_dir, f"{item_id}.{fmt}")
    return path if os.path.isfile(path) else None


def delete_item(history_dir: str, item_id: str) -> bool:
    """Remove the audio and the sidecar of `item_id`; False when the id is invalid or the json is missing."""
    if not is_valid_id(item_id):
        return False
    path = audio_path(history_dir, item_id)
    sidecar = json_path(history_dir, item_id)
    if not os.path.isfile(sidecar):
        return False
    for target in (path, sidecar):
        if target is None:
            continue
        try:
            os.remove(target)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.error(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            return False
    logger.info(f"History item {item_id} deleted")
    return True


def prune(history_dir: str, max_items: int) -> int:
    """Delete the oldest items beyond `max_items` (< 1 disables pruning); return how many were removed."""
    if max_items < 1:
        return 0
    ids = list_ids(history_dir)
    removed = 0
    for item_id in ids[max_items:]:
        if delete_item(history_dir, item_id):
            removed += 1
    if removed:
        logger.info(f"History pruned: {removed} items removed, {max_items} kept")
    return removed


def main():
    """Module entry point placeholder."""
    pass


if __name__ == "__main__":
    main()
