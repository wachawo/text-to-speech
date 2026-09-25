#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs.languages: which codes are accepted, how they are normalized and matched."""

import pytest

from libs.languages import is_language_code, language_supported, normalize_language, primary_language

# is_language_code


@pytest.mark.parametrize("value", ["en", "EN", "12", "zh-cn", "zh-CN", "pt_BR", "es-419", "en-gb", "sr-latn"])
def test_is_language_code_accepts_two_characters_and_tags(value):
    """Any 2-character string (the rule before tags) and a tag with a 2-4 character subtag are accepted."""
    assert is_language_code(value) is True


@pytest.mark.parametrize("value", ["e", "eng", "english", "zh-", "zh-c", "zh-toolong", "zh cn", "zh-cn-x", "", None, 42])
def test_is_language_code_rejects_other_shapes(value):
    """Longer words, a dangling or too long subtag, non-strings and the empty string are refused."""
    assert is_language_code(value) is False


# normalize_language


@pytest.mark.parametrize(
    "value,expected", [("EN", "en"), ("en", "en"), ("pt_BR", "pt-br"), ("ZH-CN", "zh-cn"), ("es-419", "es-419")]
)
def test_normalize_language_lowercases_and_uses_a_hyphen(value, expected):
    """Codes are lowercased and a tag separator becomes '-'."""
    assert normalize_language(value) == expected


# primary_language


@pytest.mark.parametrize("value,expected", [("pt-br", "pt"), ("pt_BR", "pt"), ("en", "en"), ("es-419", "es")])
def test_primary_language_returns_the_first_subtag(value, expected):
    """A tag is reduced to its primary subtag; a 2-character code is returned unchanged."""
    assert primary_language(value) == expected


# language_supported


def test_language_supported_when_engine_declares_nothing():
    """None means the engine does not declare its languages, so every code passes."""
    assert language_supported("xx", None) is True
    assert language_supported("xx-yy", None) is True


@pytest.mark.parametrize("language", ["en", "EN", "en-gb", "en_GB", "zh-cn"])
def test_language_supported_by_code_or_primary_subtag(language):
    """A listed code, or a tag whose primary subtag is listed, is supported."""
    assert language_supported(language, ["en", "zh-cn"]) is True


@pytest.mark.parametrize("language", ["ru", "ru-ru", "zh"])
def test_language_not_supported_when_unlisted(language):
    """A code that is not listed, directly or by its primary subtag, is not supported."""
    assert language_supported(language, ["en", "zh-cn"]) is False


def test_language_supported_matches_listed_tags_without_regard_to_case():
    """An engine that lists 'zh-CN' serves 'zh-cn'."""
    assert language_supported("zh-cn", ["zh-CN"]) is True
