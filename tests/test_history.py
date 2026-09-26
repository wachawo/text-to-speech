#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the ttssrv.history file store: save/get/list round trip, audio paths, delete, prune, id checks."""

import os
from datetime import datetime, timedelta

import pytest

# Local imports
from ttssrv import history

NOW = datetime(2025, 6, 1, 12, 0, 0)
MP3_BYTES = b"ID3" + b"\x00" * 64


def meta(text="hello", **overrides):
    """Build a save_item meta dict with sensible defaults."""
    base = {"engine": "gtts", "language": "en", "voice": None, "text": text, "elapsed": 0.123456}
    base.update(overrides)
    return base


def test_save_get_list_round_trip(tmp_path, make_wav):
    """Saved items come back from get_item in full and from list_items newest first with a cut preview."""
    long_text = "x" * 300
    first = history.save_item(str(tmp_path), make_wav(), meta("first"), NOW, 0)
    second = history.save_item(str(tmp_path), make_wav(), meta(long_text), NOW + timedelta(seconds=1), 0)

    assert history.is_valid_id(first["id"])
    assert first["created_at"] == "2025-06-01 12:00:00"
    assert first["engine"] == "gtts"
    assert first["language"] == "en"
    assert first["voice"] is None
    assert first["format"] == "wav"
    assert first["bytes"] == len(make_wav())
    assert first["text"] == "first"
    assert first["text_chars"] == 5
    assert first["elapsed"] == 0.12

    got = history.get_item(str(tmp_path), second["id"])
    assert got == second
    assert got["text"] == long_text
    assert got["text_chars"] == 300

    total, items = history.list_items(str(tmp_path), limit=10, offset=0)
    assert total == 2
    assert [item["id"] for item in items] == [second["id"], first["id"]]
    assert items[0]["text"] == "x" * 200 + "..."
    assert items[0]["text_chars"] == 300
    assert items[1]["text"] == "first"

    total, items = history.list_items(str(tmp_path), limit=1, offset=1)
    assert total == 2
    assert [item["id"] for item in items] == [first["id"]]


def test_list_items_missing_dir(tmp_path):
    """A history directory that does not exist yet lists as empty."""
    assert history.list_items(str(tmp_path / "none"), limit=10, offset=0) == (0, [])


def test_list_items_skips_unreadable_json(tmp_path, make_wav):
    """A corrupt sidecar is skipped instead of breaking the listing."""
    item = history.save_item(str(tmp_path), make_wav(), meta(), NOW, 0)
    broken_id = "20250601_115900_abcdef"
    (tmp_path / f"{broken_id}.json").write_text("{not json", encoding="utf-8")
    total, items = history.list_items(str(tmp_path), limit=10, offset=0)
    assert total == 2
    assert [entry["id"] for entry in items] == [item["id"]]
    assert history.get_item(str(tmp_path), broken_id) is None


def test_audio_path_follows_format(tmp_path, make_wav):
    """The audio file extension follows the sniffed format for both WAV and MP3 bytes."""
    wav_item = history.save_item(str(tmp_path), make_wav(), meta(), NOW, 0)
    mp3_item = history.save_item(str(tmp_path), MP3_BYTES, meta(), NOW + timedelta(seconds=1), 0)

    assert wav_item["format"] == "wav"
    assert mp3_item["format"] == "mp3"
    assert mp3_item["seconds"] is None

    wav_path = history.audio_path(str(tmp_path), wav_item["id"])
    mp3_path = history.audio_path(str(tmp_path), mp3_item["id"])
    assert wav_path == str(tmp_path / f"{wav_item['id']}.wav")
    assert mp3_path == str(tmp_path / f"{mp3_item['id']}.mp3")
    assert open(wav_path, "rb").read() == make_wav()
    assert open(mp3_path, "rb").read() == MP3_BYTES
    assert not list(tmp_path.glob("*.tmp"))


def test_audio_path_unknown_id(tmp_path):
    """A well-formed id with no sidecar resolves to no audio path."""
    assert history.audio_path(str(tmp_path), "20250601_120000_abcdef") is None


def test_delete_removes_both_files(tmp_path, make_wav):
    """delete_item removes the audio and the sidecar and reports a missing item as False."""
    item = history.save_item(str(tmp_path), make_wav(), meta(), NOW, 0)
    assert history.delete_item(str(tmp_path), item["id"]) is True
    assert list(tmp_path.iterdir()) == []
    assert history.get_item(str(tmp_path), item["id"]) is None
    assert history.delete_item(str(tmp_path), item["id"]) is False


def test_prune_keeps_newest(tmp_path, make_wav):
    """prune keeps the newest N items and removes the rest, oldest first."""
    ids = []
    for index in range(5):
        item = history.save_item(str(tmp_path), make_wav(), meta(), NOW + timedelta(seconds=index), 0)
        ids.append(item["id"])
    assert history.prune(str(tmp_path), 0) == 0
    assert history.prune(str(tmp_path), 2) == 3
    total, items = history.list_items(str(tmp_path), limit=10, offset=0)
    assert total == 2
    assert [item["id"] for item in items] == [ids[4], ids[3]]
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [f"{ids[3]}.wav", f"{ids[3]}.json", f"{ids[4]}.wav", f"{ids[4]}.json"]
    )


def test_save_item_prunes(tmp_path, make_wav):
    """save_item enforces max_items right after writing the new item."""
    for index in range(3):
        history.save_item(str(tmp_path), make_wav(), meta(), NOW + timedelta(seconds=index), 2)
    total, unused_items = history.list_items(str(tmp_path), limit=10, offset=0)
    assert total == 2


@pytest.mark.parametrize("bad_id", ["../x", "20250101_000000_zzzzzz", "", "20250101_000000_abcdef.json"])
def test_invalid_ids_refused_without_touching_dir(tmp_path, bad_id):
    """Invalid ids are refused by every accessor and the directory is never created or read."""
    missing = tmp_path / "never"
    assert history.get_item(str(missing), bad_id) is None
    assert history.audio_path(str(missing), bad_id) is None
    assert history.delete_item(str(missing), bad_id) is False
    assert not missing.exists()


def test_seconds_from_wav_header(tmp_path, make_wav):
    """A one-second 22050 Hz WAV reports 1.0 seconds."""
    audio = make_wav(duration_ms=1000, rate=22050)
    assert history.audio_seconds(audio, "wav") == 1.0
    item = history.save_item(str(tmp_path), audio, meta(), NOW, 0)
    assert item["seconds"] == 1.0


def test_seconds_malformed_wav():
    """A RIFF header without a valid WAV body yields None instead of raising."""
    assert history.audio_seconds(b"RIFF" + b"\x00" * 10, "wav") is None
    assert history.audio_seconds(MP3_BYTES, "mp3") is None


def test_audio_format_sniffing(make_wav):
    """audio_format recognizes ID3 and frame-sync MP3, RIFF WAV and everything else as bin."""
    assert history.audio_format(MP3_BYTES) == "mp3"
    assert history.audio_format(b"\xff\xfb" + b"\x00" * 8) == "mp3"
    # Tagless MPEG-2 layer III, which is what gTTS returns.
    assert history.audio_format(b"\xff\xf3\x64\xc4" + b"\x00" * 8) == "mp3"
    assert history.audio_format(b"\xff") == "bin"
    assert history.audio_format(b"\xff\x00" + b"\x00" * 8) == "bin"
    assert history.audio_format(make_wav()) == "wav"
    assert history.audio_format(b"\x00\x01\x02") == "bin"


@pytest.mark.parametrize(
    "item_id, expected",
    [
        ("20250601_120000_abcdef", True),
        ("20250601_120000_012345", True),
        ("20250601_120000_ABCDEF", False),
        ("20250601_120000_abcde", False),
        ("20250601_120000_abcdefa", False),
        ("2025060_120000_abcdef", False),
        ("20250601-120000_abcdef", False),
        ("../20250601_120000_abcdef", False),
        ("20250601_120000_abcdef\n", False),
        ("", False),
        (None, False),
    ],
)
def test_is_valid_id(item_id, expected):
    """is_valid_id accepts exactly the <8 digits>_<6 digits>_<6 lowercase hex> shape."""
    assert history.is_valid_id(item_id) is expected


def test_new_item_id_shape():
    """new_item_id embeds the timestamp and a six-character hex suffix."""
    item_id = history.new_item_id(NOW)
    assert item_id.startswith("20250601_120000_")
    assert history.is_valid_id(item_id)
    assert history.new_item_id(NOW) != item_id


def test_audio_written_before_json(tmp_path, make_wav, monkeypatch):
    """The sidecar is written after the audio so a crash in between leaves no orphan json."""
    order = []
    real_write = history.write_atomic

    def tracking_write(path, data):
        """Record the extension of every atomic write."""
        order.append(os.path.splitext(path)[1])
        real_write(path, data)

    monkeypatch.setattr(history, "write_atomic", tracking_write)
    history.save_item(str(tmp_path), make_wav(), meta(), NOW, 0)
    assert order == [".wav", ".json"]


def test_write_atomic_leaves_no_tmp_file_when_the_write_fails(tmp_path):
    """A failed write removes its .tmp neighbour: no listing sees it, so nothing would ever prune it."""
    target = tmp_path / "item.wav"
    with pytest.raises(TypeError):
        history.write_atomic(str(target), "not bytes")  # type: ignore[arg-type]
    assert list(tmp_path.iterdir()) == []


def test_write_atomic_replaces_the_target(tmp_path):
    """The data lands at the target and the .tmp neighbour is gone."""
    target = tmp_path / "item.wav"
    history.write_atomic(str(target), b"RIFF")
    assert target.read_bytes() == b"RIFF"
    assert list(tmp_path.iterdir()) == [target]
