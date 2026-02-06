#!/usr/bin/env python3
"""
TTS Library Tests - Functional Test Suite

Comprehensive functional test suite for the TTS library covering:
- Pure function testing
- Function composition testing
- Pipeline testing
- Error handling testing
- Integration testing

Author: TTS Library Team
Version: 1.0.0
License: MIT
"""

import unittest
import tempfile
import os
import sys
from unittest.mock import patch
import logging
from typing import List, Any, Callable

# Configure logging for tests
logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stderr)],
    level=logging.WARNING,
    format="%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s.%(funcName)s) - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

try:
    from libs.api import (  # type: ignore
        text_to_speech_file,
        text_to_speech_bytes,
        text_to_speech_bytesio,
    )
    from libs.tools import (
        validate_text,
        validate_engine,
        validate_language,
        get_default_config,
        compose,
        with_engine,
        with_language,
        create_tts_pipeline,
        batch_tts,
        generate_timestamp_filename,
        ensure_audio_directory,
    )
    from libs.exceptions import TTSException, ValidationError, EngineNotAvailableError
except ImportError as e:
    logger.error(f"Failed to import TTS library: {e}")
    sys.exit(1)


# Functional test utilities
def create_test_case(name: str, test_func: Callable) -> type:
    """Create a test case dynamically."""

    class DynamicTestCase(unittest.TestCase):
        def runTest(self):
            test_func(self)

    DynamicTestCase.__name__ = name
    return DynamicTestCase


def assert_equal(actual: Any, expected: Any, message: str = "") -> None:
    """Functional assertion helper."""
    if actual != expected:
        raise AssertionError(f"{message}: Expected {expected}, got {actual}")


def assert_raises(
    exception_class: type[BaseException], func: Callable, *args: Any, **kwargs: Any
) -> None:
    """Functional exception assertion helper."""
    try:
        func(*args, **kwargs)
        raise AssertionError(f"Expected {exception_class.__name__} to be raised")
    except exception_class:
        pass


def assert_true(condition: bool, message: str = "") -> None:
    """Functional truth assertion helper."""
    if not condition:
        raise AssertionError(f"Expected True, got False: {message}")


def assert_false(condition: bool, message: str = "") -> None:
    """Functional false assertion helper."""
    if condition:
        raise AssertionError(f"Expected False, got True: {message}")


# Pure function tests
def test_validate_text_valid():
    """Test valid text validation."""
    result = validate_text("Hello world")
    assert_equal(result, "Hello world", "Valid text should be returned unchanged")


def test_validate_text_empty():
    """Test empty text validation."""
    assert_raises(ValidationError, validate_text, "")


def test_validate_text_whitespace():
    """Test whitespace-only text validation."""
    assert_raises(ValidationError, validate_text, "   ")


def test_validate_text_too_long():
    """Test text length validation."""
    long_text = "a" * 5001
    assert_raises(ValidationError, validate_text, long_text)


def test_validate_text_non_string():
    """Test non-string input validation."""
    assert_raises(ValidationError, validate_text, 123)


def test_validate_engine_valid():
    """Test valid engine validation."""
    with patch("engines.is_engine_available", return_value=True):
        result = validate_engine("gtts")
        assert_equal(result, "gtts", "Valid engine should be returned")


def test_validate_engine_invalid():
    """Test invalid engine validation."""
    assert_raises(ValidationError, validate_engine, "invalid_engine")


def test_validate_language_valid():
    """Test valid language validation."""
    result = validate_language("en")
    assert_equal(result, "en", "Valid language should be returned")


def test_validate_language_invalid():
    """Test invalid language validation."""
    assert_raises(ValidationError, validate_language, "english")


def test_get_default_config():
    """Test default configuration."""
    config = get_default_config()
    assert_true(isinstance(config, dict), "Config should be a dictionary")
    assert_true("engine" in config, "Config should contain engine")
    assert_true("language" in config, "Config should contain language")
    assert_true("rate" in config, "Config should contain rate")
    assert_true("volume" in config, "Config should contain volume")


def test_generate_timestamp_filename():
    """Test timestamp filename generation."""
    filename = generate_timestamp_filename("", "mp3")
    assert_true(filename.endswith(".mp3"), "Filename should end with .mp3")
    assert_true(
        len(filename) == 19, "Filename should be 19 characters long"
    )  # YYYYMMDD_HHMMSS.mp3

    filename_with_prefix = generate_timestamp_filename("test", "mp3")
    assert_true(
        filename_with_prefix.startswith("test_"), "Filename should start with prefix"
    )
    assert_true(filename_with_prefix.endswith(".mp3"), "Filename should end with .mp3")


def test_ensure_audio_directory():
    """Test audio directory creation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = os.path.join(temp_dir, "test_audio")
        result = ensure_audio_directory(test_dir)
        assert_equal(result, test_dir, "Should return the directory path")
        assert_true(os.path.exists(test_dir), "Directory should exist")


# Function composition tests
def test_compose_functions():
    """Test function composition."""

    def add_one(x):
        return x + 1

    def multiply_two(x):
        return x * 2

    composed = compose(add_one, multiply_two)
    result = composed(5)  # Should be (5 * 2) + 1 = 11
    assert_equal(result, 11, "Composed function should work correctly")


def test_with_engine():
    """Test with_engine higher-order function."""

    def mock_tts_function(text, engine=None, **kwargs):
        return engine

    offline_tts = with_engine("pyttsx3")(mock_tts_function)
    result = offline_tts("test")
    assert_equal(result, "pyttsx3", "Engine should be set correctly")


def test_with_language():
    """Test with_language higher-order function."""

    def mock_tts_function(text, language=None, **kwargs):
        return language

    spanish_tts = with_language("es")(mock_tts_function)
    result = spanish_tts("test")
    assert_equal(result, "es", "Language should be set correctly")


# TTS function tests
def test_text_to_speech_file_success():
    """Test successful text to speech file generation."""
    with patch("engines.is_engine_available", return_value=True):
        with patch("engines.gtts.generate") as mock_generate:
            mock_generate.return_value = b"fake_audio_data"

            result = text_to_speech_file("Hello world", "test.mp3", "gtts", "en")

            assert result.endswith(".mp3"), "Should create mp3 file"
            assert_true(mock_generate.called, "generate should be called")


def test_text_to_speech_bytes_success():
    """Test successful text to speech bytes generation."""
    with patch("engines.is_engine_available", return_value=True):
        with patch("engines.gtts.generate") as mock_generate:
            mock_generate.return_value = b"fake_audio_data"

            result = text_to_speech_bytes("Hello world", "gtts", "en")

            assert_equal(result, b"fake_audio_data", "Should return audio bytes")
            assert_true(mock_generate.called, "generate should be called")


def test_text_to_speech_bytesio_success():
    """Test successful text to speech BytesIO generation."""
    with patch("engines.is_engine_available", return_value=True):
        with patch("engines.gtts.generate") as mock_generate:
            mock_generate.return_value = b"fake_audio_data"

            result = text_to_speech_bytesio("Hello world", "gtts", "en")

            assert_equal(
                result.getvalue(),
                b"fake_audio_data",
                "Should return BytesIO with correct data",
            )
            assert_true(mock_generate.called, "generate should be called")


# Pipeline tests
def test_create_tts_pipeline_file():
    """Test TTS pipeline file output."""
    with patch("engines.is_engine_available", return_value=True):
        with patch("engines.gtts.generate") as mock_generate:
            mock_generate.return_value = b"fake_audio_data"

            pipeline = create_tts_pipeline("gtts", "en")
            result = pipeline("Hello world", "file", "test.mp3")

            assert result.endswith(".mp3"), "Pipeline should create file"
            assert_true(mock_generate.called, "generate should be called")


def test_create_tts_pipeline_bytes():
    """Test TTS pipeline bytes output."""
    with patch("engines.is_engine_available", return_value=True):
        with patch("engines.gtts.generate") as mock_generate:
            mock_generate.return_value = b"fake_audio_data"

            pipeline = create_tts_pipeline("gtts", "en")
            result = pipeline("Hello world", "bytes")

            assert_equal(result, b"fake_audio_data", "Pipeline should return bytes")
            assert_true(mock_generate.called, "generate should be called")


# Batch processing tests
def test_batch_tts_success():
    """Test successful batch processing."""
    with patch("engines.is_engine_available", return_value=True):
        with patch("engines.gtts.generate") as mock_generate:
            mock_generate.return_value = b"fake_audio_data"

            with tempfile.TemporaryDirectory() as temp_dir:
                texts = ["Hello", "World", "Test"]
                result = batch_tts(texts, output_dir=temp_dir, engine="gtts")

                assert_equal(len(result), 3, "Should return 3 filenames")
                assert_true(
                    all(filename.endswith(".mp3") for filename in result),
                    "All filenames should end with .mp3",
                )
                assert_equal(
                    mock_generate.call_count, 3, "generate should be called 3 times"
                )


def test_batch_tts_empty_list():
    """Test batch processing with empty list."""
    assert_raises(ValidationError, batch_tts, [])


def test_batch_tts_invalid_input():
    """Test batch processing with invalid input."""
    assert_raises(ValidationError, batch_tts, "not_a_list")


# Error handling tests
def test_tts_exception():
    """Test TTS exception."""
    assert_raises(TTSException, lambda: exec('raise TTSException("Test error")'))


def test_validation_error():
    """Test validation error."""
    assert_raises(
        ValidationError, lambda: exec('raise ValidationError("Test validation error")')
    )


def test_engine_not_available_error():
    """Test engine not available error."""
    assert_raises(
        EngineNotAvailableError,
        lambda: exec('raise EngineNotAvailableError("Test engine error")'),
    )


# Integration tests
def test_full_workflow_mock():
    """Test full workflow with mocked dependencies."""
    with patch("engines.gtts.AVAILABLE", True):
        with patch("engines.gtts.generate") as mock_generate:
            # Mock generate to return fake audio bytes
            mock_generate.return_value = b"fake_audio_data"

            # Test full workflow
            audio_bytes = text_to_speech_bytes("Hello world", engine="gtts")
            assert audio_bytes == b"fake_audio_data", "Should return mocked audio bytes"

            # Test pipeline
            pipeline = create_tts_pipeline(engine="gtts")
            result = pipeline("Hello world", "bytes")
            assert_equal(result, b"fake_audio_data", "Pipeline should return bytes")


# Test runner functions
def run_validation_tests() -> List[bool]:
    """Run all validation tests."""
    tests = [
        test_validate_text_valid,
        test_validate_text_empty,
        test_validate_text_whitespace,
        test_validate_text_too_long,
        test_validate_text_non_string,
        test_validate_engine_valid,
        test_validate_engine_invalid,
        test_validate_language_valid,
        test_validate_language_invalid,
        test_get_default_config,
    ]

    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"Test {test.__name__} failed: {e}")
            results.append(False)

    return results


def run_utility_tests() -> List[bool]:
    """Run all utility tests."""
    tests = [test_generate_timestamp_filename, test_ensure_audio_directory]

    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"Test {test.__name__} failed: {e}")
            results.append(False)

    return results


def run_composition_tests() -> List[bool]:
    """Run all function composition tests."""
    tests = [test_compose_functions, test_with_engine, test_with_language]

    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"Test {test.__name__} failed: {e}")
            results.append(False)

    return results


def run_tts_tests() -> List[bool]:
    """Run all TTS function tests."""
    tests = [
        test_text_to_speech_file_success,
        test_text_to_speech_bytes_success,
        test_text_to_speech_bytesio_success,
    ]

    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"Test {test.__name__} failed: {e}")
            results.append(False)

    return results


def run_pipeline_tests() -> List[bool]:
    """Run all pipeline tests."""
    tests = [test_create_tts_pipeline_file, test_create_tts_pipeline_bytes]

    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"Test {test.__name__} failed: {e}")
            results.append(False)

    return results


def run_batch_tests() -> List[bool]:
    """Run all batch processing tests."""
    tests = [
        test_batch_tts_success,
        test_batch_tts_empty_list,
        test_batch_tts_invalid_input,
    ]

    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"Test {test.__name__} failed: {e}")
            results.append(False)

    return results


def run_error_tests() -> List[bool]:
    """Run all error handling tests."""
    tests = [test_tts_exception, test_validation_error, test_engine_not_available_error]

    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"Test {test.__name__} failed: {e}")
            results.append(False)

    return results


def run_integration_tests() -> List[bool]:
    """Run all integration tests."""
    tests = [test_full_workflow_mock]

    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"Test {test.__name__} failed: {e}")
            results.append(False)

    return results


def run_all_tests() -> bool:
    """Run all tests and return success status."""
    print("TTS Library Functional Test Suite")
    print("=" * 50)

    test_categories = [
        ("Validation Tests", run_validation_tests),
        ("Utility Tests", run_utility_tests),
        ("Composition Tests", run_composition_tests),
        ("TTS Function Tests", run_tts_tests),
        ("Pipeline Tests", run_pipeline_tests),
        ("Batch Tests", run_batch_tests),
        ("Error Handling Tests", run_error_tests),
        ("Integration Tests", run_integration_tests),
    ]

    all_results = []

    for category_name, test_runner in test_categories:
        print(f"\nRunning {category_name}...")
        results = test_runner()
        passed = sum(results)
        total = len(results)
        print(f"  Passed: {passed}/{total}")
        all_results.extend(results)

    total_passed = sum(all_results)
    total_tests = len(all_results)

    print("\nTest Summary:")
    print(f"  Total tests: {total_tests}")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_tests - total_passed}")

    success = total_passed == total_tests

    if success:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed!")

    return success


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
