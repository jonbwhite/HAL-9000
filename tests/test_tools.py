# ABOUTME: Tests for Discord message fetching tools
# ABOUTME: Uses mocked Discord API to test tool functionality

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, Mock, MagicMock
import discord
from tools import fetch_messages_tool, FetchMessagesParams, MessageData


@pytest.fixture
def mock_discord_client():
    """Create a mocked Discord client."""
    client = Mock(spec=discord.Client)
    return client


@pytest.fixture
def mock_text_channel():
    """Create a mocked Discord text channel."""
    channel = Mock(spec=discord.TextChannel)
    channel.id = 123456789
    return channel


@pytest.fixture
def mock_messages():
    """Create mock Discord messages."""
    messages = []
    base_time = datetime.now(UTC) - timedelta(hours=2)

    for i in range(5):
        msg = Mock(spec=discord.Message)
        msg.author = Mock()
        msg.author.display_name = f"User{i}"
        msg.author.bot = False
        msg.content = f"Test message {i}"
        msg.created_at = base_time + timedelta(minutes=i*10)
        messages.append(msg)

    return messages


@pytest.mark.asyncio
async def test_fetch_messages_success(mock_discord_client, mock_text_channel, mock_messages):
    """Tool should successfully fetch messages from channel."""
    mock_discord_client.get_channel.return_value = mock_text_channel

    # Mock the async iteration
    async def async_generator():
        for msg in reversed(mock_messages):  # history returns newest first
            yield msg

    mock_text_channel.history.return_value = async_generator()

    params = FetchMessagesParams(channel_id=123456789, hours_back=24, limit=100)
    result = await fetch_messages_tool(params, mock_discord_client)

    assert len(result) == 5
    assert all(isinstance(msg, MessageData) for msg in result)
    assert result[0].content == "Test message 0"  # Oldest first
    assert result[4].content == "Test message 4"  # Newest last


@pytest.mark.asyncio
async def test_fetch_messages_channel_not_found(mock_discord_client):
    """Tool should raise error if channel not found."""
    mock_discord_client.get_channel.return_value = None

    params = FetchMessagesParams(channel_id=999999, hours_back=24)

    with pytest.raises(ValueError) as exc_info:
        await fetch_messages_tool(params, mock_discord_client)

    assert "not found or not accessible" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_messages_not_text_channel(mock_discord_client):
    """Tool should raise error if channel is not a text channel."""
    voice_channel = Mock(spec=discord.VoiceChannel)
    mock_discord_client.get_channel.return_value = voice_channel

    params = FetchMessagesParams(channel_id=123456, hours_back=24)

    with pytest.raises(ValueError) as exc_info:
        await fetch_messages_tool(params, mock_discord_client)

    assert "not a text channel" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_messages_filters_bots(mock_discord_client, mock_text_channel):
    """Tool should filter out bot messages."""
    messages = []
    for i in range(3):
        msg = Mock(spec=discord.Message)
        msg.author = Mock()
        msg.author.display_name = f"User{i}"
        msg.author.bot = i == 1  # Middle message is from bot
        msg.content = f"Message {i}"
        msg.created_at = datetime.now(UTC)
        messages.append(msg)

    mock_discord_client.get_channel.return_value = mock_text_channel

    async def async_generator():
        for msg in messages:
            yield msg

    mock_text_channel.history.return_value = async_generator()

    params = FetchMessagesParams(channel_id=123456, hours_back=24, limit=100)
    result = await fetch_messages_tool(params, mock_discord_client)

    assert len(result) == 2
    assert all(msg.author != "User1" for msg in result)


def test_fetch_messages_params_validation():
    """Parameters should validate constraints."""
    # Valid params
    params = FetchMessagesParams(channel_id=123, hours_back=24)
    assert params.hours_back == 24

    # Invalid hours (too low)
    with pytest.raises(Exception):  # Pydantic ValidationError
        FetchMessagesParams(channel_id=123, hours_back=0)

    # Invalid hours (too high)
    with pytest.raises(Exception):
        FetchMessagesParams(channel_id=123, hours_back=200)
