# ABOUTME: Tests for recent message context fetching
# ABOUTME: Validates automatic context fetching for agent

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, Mock
import discord
from agent import fetch_recent_messages
from tools import MessageData


@pytest.fixture
def mock_text_channel():
    """Create a mocked Discord text channel."""
    channel = Mock(spec=discord.TextChannel)
    channel.id = 123456789
    return channel


@pytest.fixture
def mock_messages():
    """Create mock Discord messages within recent time window."""
    messages = []
    base_time = datetime.now(UTC) - timedelta(minutes=2)

    for i in range(5):
        msg = Mock(spec=discord.Message)
        msg.author = Mock()
        msg.author.display_name = f"User{i}"
        msg.author.bot = i == 2  # Third message is from bot
        msg.content = f"Test message {i}"
        msg.created_at = base_time + timedelta(minutes=i*0.5)
        messages.append(msg)

    return messages


@pytest.mark.asyncio
async def test_fetch_recent_messages_success(mock_text_channel, mock_messages):
    """Should successfully fetch recent messages from channel."""
    # Mock the async iteration
    async def async_generator():
        for msg in reversed(mock_messages):  # history returns newest first
            yield msg

    mock_text_channel.history.return_value = async_generator()

    result = await fetch_recent_messages(mock_text_channel, minutes_back=5, limit=10)

    assert len(result) == 5
    assert all(isinstance(msg, MessageData) for msg in result)
    assert result[0].content == "Test message 0"  # Oldest first
    assert result[4].content == "Test message 4"  # Newest last


@pytest.mark.asyncio
async def test_fetch_recent_messages_includes_bots(mock_text_channel, mock_messages):
    """Should include bot messages in recent context."""
    async def async_generator():
        for msg in reversed(mock_messages):
            yield msg

    mock_text_channel.history.return_value = async_generator()

    result = await fetch_recent_messages(mock_text_channel, minutes_back=5, limit=10)

    # Should include all 5 messages including the bot message
    assert len(result) == 5
    # Verify bot message is included (User2 is the bot)
    bot_messages = [msg for msg in result if msg.author == "User2"]
    assert len(bot_messages) == 1


@pytest.mark.asyncio
async def test_fetch_recent_messages_time_window_filtering(mock_text_channel):
    """Should only include messages within the time window."""
    now = datetime.now(UTC)
    
    # Create messages: 2 within window, 1 outside
    all_messages = []
    for i, minutes_ago in enumerate([1, 3, 7]):  # 1 and 3 are within 5 min window, 7 is not
        msg = Mock(spec=discord.Message)
        msg.author = Mock()
        msg.author.display_name = f"User{i}"
        msg.author.bot = False
        msg.content = f"Message {i}"
        msg.created_at = now - timedelta(minutes=minutes_ago)
        all_messages.append(msg)

    # Mock history to filter by 'after' parameter (simulating Discord's behavior)
    def history_mock(limit=None, after=None, **kwargs):
        async def async_generator():
            filtered = [msg for msg in all_messages if after is None or msg.created_at > after]
            # Sort by newest first (as Discord does)
            filtered.sort(key=lambda m: m.created_at, reverse=True)
            # Apply limit
            if limit:
                filtered = filtered[:limit]
            for msg in filtered:
                yield msg
        return async_generator()

    mock_text_channel.history = history_mock

    result = await fetch_recent_messages(mock_text_channel, minutes_back=5, limit=10)

    # Should only include messages from last 5 minutes
    assert len(result) == 2
    assert all(msg.content in ["Message 0", "Message 1"] for msg in result)


@pytest.mark.asyncio
async def test_fetch_recent_messages_limit(mock_text_channel):
    """Should respect message limit."""
    now = datetime.now(UTC)
    
    # Create 15 messages within window
    all_messages = []
    for i in range(15):
        msg = Mock(spec=discord.Message)
        msg.author = Mock()
        msg.author.display_name = f"User{i}"
        msg.author.bot = False
        msg.content = f"Message {i}"
        msg.created_at = now - timedelta(minutes=15-i)  # Spread over time
        all_messages.append(msg)

    # Mock history to respect limit parameter (simulating Discord's behavior)
    def history_mock(limit=None, after=None, **kwargs):
        async def async_generator():
            filtered = [msg for msg in all_messages if after is None or msg.created_at > after]
            # Sort by newest first (as Discord does)
            filtered.sort(key=lambda m: m.created_at, reverse=True)
            # Apply limit
            if limit:
                filtered = filtered[:limit]
            for msg in filtered:
                yield msg
        return async_generator()

    mock_text_channel.history = history_mock

    result = await fetch_recent_messages(mock_text_channel, minutes_back=20, limit=10)

    # Should only return 10 messages (the limit)
    assert len(result) == 10
    # Should be the newest 10 (since history returns newest first)
    assert result[-1].content == "Message 14"  # Newest


@pytest.mark.asyncio
async def test_fetch_recent_messages_empty_on_error(mock_text_channel):
    """Should return empty list when channel history fails."""
    # Simulate error by making history raise an exception
    async def async_generator():
        raise discord.DiscordException("Network error")
        if False:
            yield  # Make it a generator

    mock_text_channel.history.return_value = async_generator()

    result = await fetch_recent_messages(mock_text_channel, minutes_back=5, limit=10)

    assert result == []


@pytest.mark.asyncio
async def test_fetch_recent_messages_no_messages(mock_text_channel):
    """Should return empty list when no messages in time window."""
    async def async_generator():
        if False:
            yield  # Make it a generator

    mock_text_channel.history.return_value = async_generator()

    result = await fetch_recent_messages(mock_text_channel, minutes_back=5, limit=10)

    assert result == []

