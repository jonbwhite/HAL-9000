# ABOUTME: Tests for utility functions
# ABOUTME: Validates message chunking and time calculations

import pytest
from datetime import datetime, timedelta
from utils import chunk_message, get_time_window


def test_chunk_message_short_text():
    """Short text should return single chunk."""
    text = "This is a short message"
    chunks = chunk_message(text)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_message_at_paragraph_boundary():
    """Long text should split at paragraph boundaries."""
    para1 = "A" * 1500
    para2 = "B" * 1500
    text = f"{para1}\n\n{para2}"

    chunks = chunk_message(text, max_length=2000)

    assert len(chunks) == 2
    assert para1 in chunks[0]
    assert para2 in chunks[1]


def test_chunk_message_at_sentence_boundary():
    """Text without paragraphs should split at sentences."""
    sent1 = "A" * 1500 + "."
    sent2 = "B" * 1500 + "."
    text = f"{sent1} {sent2}"

    chunks = chunk_message(text, max_length=2000)

    assert len(chunks) == 2
    assert "A" * 1500 in chunks[0]
    assert "B" * 1500 in chunks[1]


def test_chunk_message_at_word_boundary():
    """Text without sentences should split at words."""
    text = " ".join(["word"] * 500)

    chunks = chunk_message(text, max_length=2000)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 2000


def test_chunk_message_force_split():
    """Very long word should force character split."""
    text = "A" * 3000

    chunks = chunk_message(text, max_length=2000)

    assert len(chunks) == 2
    assert len(chunks[0]) == 2000
    assert len(chunks[1]) == 1000


def test_get_time_window():
    """Time window should calculate correct past datetime."""
    from datetime import UTC
    before = datetime.now(UTC)
    window = get_time_window(24)
    after = datetime.now(UTC)

    expected_min = before - timedelta(hours=24, seconds=1)
    expected_max = after - timedelta(hours=24)

    assert expected_min <= window <= expected_max
