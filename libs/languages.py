#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Language code rules shared by the validators, the engines and the HTTP server."""

import re

# A language with a region or script subtag: `zh-cn`, `pt_BR`, `en-gb`, `es-419`.
LANGUAGE_TAG_REGEX = re.compile(r"[A-Za-z]{2}[-_][A-Za-z0-9]{2,4}")


def is_language_code(value: object) -> bool:
    """Return True for any 2-character string (the rule before tags) or a tag such as 'zh-cn' or 'pt_BR'."""
    if not isinstance(value, str):
        return False
    return len(value) == 2 or LANGUAGE_TAG_REGEX.fullmatch(value) is not None


def normalize_language(value: str) -> str:
    """Lowercase a language code; a tag also gets '-' in place of '_' ('pt_BR' -> 'pt-br').

    A 2-character code is only lowercased, as it was before tags were accepted.
    """
    if len(value) == 2:
        return value.lower()
    return value.lower().replace("_", "-")


def primary_language(value: str) -> str:
    """Return the primary subtag of a tag ('pt-br' or 'pt_BR' -> 'pt'); a 2-character code is returned unchanged."""
    if len(value) == 2:
        return value
    return normalize_language(value).split("-", 1)[0]


def language_supported(language: str, languages: list[str] | None) -> bool:
    """Report whether an engine that declares `languages` serves `language`.

    None means the engine does not declare its languages, so every code passes.
    Otherwise the normalized code or its primary subtag has to be listed:
    'en-gb' passes for an engine that lists 'en'.
    """
    if languages is None:
        return True
    code = normalize_language(language)
    listed = {normalize_language(item) for item in languages}
    return code in listed or primary_language(code) in listed


def main():
    """Module entrypoint placeholder, this file is import-only."""
    pass


if __name__ == "__main__":
    main()
