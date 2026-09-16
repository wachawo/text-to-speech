#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers behind the OpenAI-compatible /v1 audio routes: name mapping, error shape, ffmpeg transcoding."""

import functools
import logging
import shutil
import subprocess
import traceback

logger = logging.getLogger(__name__)

# OpenAI model names every client knows; each one means "the default engine here".
OPENAI_MODELS = ("tts-1", "tts-1-hd", "gpt-4o-mini-tts")
# OpenAI voice names; each one means "the engine default voice".
OPENAI_VOICES = ("alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse")
# response_format -> (Content-Type, ffmpeg output arguments). PCM is what OpenAI
# serves: signed 16-bit little-endian mono at 24 kHz.
RESPONSE_FORMATS = {
    "mp3": ("audio/mpeg", ["-f", "mp3"]),
    "wav": ("audio/wav", ["-f", "wav"]),
    "pcm": ("audio/pcm", ["-f", "s16le", "-ar", "24000", "-ac", "1"]),
    "opus": ("audio/opus", ["-f", "opus"]),
    "flac": ("audio/flac", ["-f", "flac"]),
    "aac": ("audio/aac", ["-f", "adts"]),
}
FFMPEG_TIMEOUT = 120


class OpenAIRequestError(Exception):
    """A request the /v1 routes refuse, carrying the OpenAI error fields and the HTTP status."""

    def __init__(self, message: str, param: str | None = None, status: int = 400, error_type: str = "invalid_request_error"):
        super().__init__(message)
        self.message = message
        self.param = param
        self.status = status
        self.error_type = error_type


def error_body(message: str, param: str | None = None, error_type: str = "invalid_request_error") -> dict:
    """Build the OpenAI error envelope: {"error": {"message", "type", "param", "code"}}."""
    return {"error": {"message": message, "type": error_type, "param": param, "code": None}}


def validation_error_body(messages: dict | list) -> dict:
    """Turn Marshmallow's `messages` into the OpenAI envelope, naming the first failing field as `param`."""
    if not isinstance(messages, dict) or not messages:
        return error_body(str(messages))
    param = sorted(messages.keys())[0]
    detail = messages[param]
    if isinstance(detail, list):
        detail = " ".join(str(item) for item in detail)
    return error_body(f"{param}: {detail}", param=str(param))


def map_model_name(model: str | None, default_engine: str) -> str:
    """Return the engine an OpenAI `model` value stands for (OpenAI names and an empty value mean the default)."""
    if not model or model in OPENAI_MODELS:
        return default_engine
    return model


def map_voice_name(voice: str | None) -> str | None:
    """Return the engine voice for an OpenAI `voice` value (OpenAI names mean the engine default, None)."""
    if not voice or voice.lower() in OPENAI_VOICES:
        return None
    return voice


def ffmpeg_available() -> bool:
    """Report whether an ffmpeg binary is on PATH."""
    return shutil.which("ffmpeg") is not None


def atempo_chain(speed: float) -> str:
    """Build an ffmpeg atempo filter for `speed`, chaining stages since one stage only covers 0.5..2.0."""
    stages = []
    while speed > 2.0:
        stages.append(2.0)
        speed /= 2.0
    while speed < 0.5:
        stages.append(0.5)
        speed /= 0.5
    stages.append(round(speed, 4))
    return ",".join(f"atempo={stage}" for stage in stages)


def ffmpeg_command(response_format: str, speed: float = 1.0) -> list[str]:
    """Build the ffmpeg argv that reads any audio on stdin and writes `response_format` to stdout."""
    command = ["ffmpeg", "-loglevel", "error", "-i", "pipe:0"]
    if speed != 1.0:
        command += ["-filter:a", atempo_chain(speed)]
    command += RESPONSE_FORMATS[response_format][1]
    command.append("pipe:1")
    return command


def transcode(audio_bytes: bytes, response_format: str, speed: float = 1.0) -> bytes:
    """Run ffmpeg over stdin/stdout to convert `audio_bytes` to `response_format` at `speed`.

    Raises:
        OpenAIRequestError: ffmpeg failed, timed out or could not be started (answered as 500).
    """
    command = ffmpeg_command(response_format, speed)
    try:
        result = subprocess.run(command, input=audio_bytes, capture_output=True, check=True, timeout=FFMPEG_TIMEOUT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        stderr = getattr(exc, "stderr", None) or b""
        logger.error(f"{type(exc).__name__}: {exc}\n{stderr.decode(errors='replace')}\n{traceback.format_exc()}")
        raise OpenAIRequestError("Audio transcoding failed", status=500, error_type="server_error") from exc
    return result.stdout


@functools.lru_cache(maxsize=1)
def warn_speed_ignored() -> None:
    """Log once per process that `speed` is ignored because ffmpeg is missing."""
    logger.warning("ffmpeg is not installed: the `speed` field of /v1/audio/speech is ignored")


def prepare_audio(audio_bytes: bytes, native_format: str, response_format: str, speed: float = 1.0) -> tuple[bytes, str]:
    """Return (audio, mimetype) in `response_format`, transcoding with ffmpeg only when needed.

    Args:
        audio_bytes: What the engine produced.
        native_format: Its sniffed format ("wav", "mp3" or "bin").
        response_format: One of RESPONSE_FORMATS.
        speed: Playback speed; anything but 1.0 needs ffmpeg and is ignored without it.

    Raises:
        OpenAIRequestError: The format differs from the native one and ffmpeg is missing.
    """
    mimetype = RESPONSE_FORMATS[response_format][0]
    same_format = native_format == response_format
    if same_format and speed == 1.0:
        return audio_bytes, mimetype
    if not ffmpeg_available():
        if not same_format:
            raise OpenAIRequestError(
                f"response_format '{response_format}' needs ffmpeg, which is not installed on this server; "
                f"ask for '{native_format}' instead",
                param="response_format",
            )
        warn_speed_ignored()
        return audio_bytes, mimetype
    return transcode(audio_bytes, response_format, speed), mimetype


def main():
    """Module entry point placeholder."""
    pass


if __name__ == "__main__":
    main()
