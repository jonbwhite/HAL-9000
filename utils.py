# ABOUTME: Utility functions for message processing
# ABOUTME: Handles message chunking and time window calculations

from datetime import datetime, timedelta
from typing import List


def chunk_message(text: str, max_length: int = 2000) -> List[str]:
    """
    Split text into chunks that fit Discord's message length limit.

    Attempts to split at paragraph boundaries first, then sentences,
    then words, and finally by character if necessary.

    Args:
        text: Text to chunk
        max_length: Maximum length per chunk (default 2000 for Discord)

    Returns:
        List of text chunks, each under max_length
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try to split at paragraph boundary
        chunk = remaining[:max_length]
        split_pos = chunk.rfind('\n\n')

        # Try sentence boundary if no paragraph
        if split_pos == -1:
            split_pos = chunk.rfind('. ')
            if split_pos != -1:
                split_pos += 1  # Include the period

        # Try any whitespace if no sentence
        if split_pos == -1:
            split_pos = chunk.rfind(' ')

        # Force split if no good boundary found
        if split_pos == -1:
            split_pos = max_length

        chunks.append(remaining[:split_pos].strip())
        remaining = remaining[split_pos:].strip()

    return chunks


def get_time_window(hours: int) -> datetime:
    """
    Calculate datetime for messages to fetch from.

    Args:
        hours: Number of hours back to fetch

    Returns:
        Datetime representing the start of the time window
    """
    from datetime import UTC
    return datetime.now(UTC) - timedelta(hours=hours)
