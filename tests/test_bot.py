# ABOUTME: Tests for Discord bot message handling
# ABOUTME: Validates mention detection, error handling, response chunking

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import discord
from bot import on_message, send_error_message, send_chunked_response, main


@pytest.fixture
def mock_client():
    """Create mocked Discord client."""
    client = Mock(spec=discord.Client)
    client.user = Mock()
    client.user.id = 999999
    return client


@pytest.fixture
def mock_message(mock_client):
    """Create mocked Discord message."""
    message = Mock(spec=discord.Message)
    message.author = Mock()
    message.author.id = 111111
    message.author.display_name = "TestUser"
    message.author.bot = False
    message.content = ""
    message.created_at = None  # Will be set in tests that need it
    message.channel = Mock(spec=discord.TextChannel)
    message.channel.id = 123456
    message.channel.send = AsyncMock()
    message.channel.guild = Mock()
    message.channel.guild.text_channels = []

    # Create async context manager for typing
    typing_context = AsyncMock()
    typing_context.__aenter__ = AsyncMock(return_value=None)
    typing_context.__aexit__ = AsyncMock(return_value=None)
    message.channel.typing = Mock(return_value=typing_context)

    message.mentions = []
    message.reference = None
    return message


@pytest.mark.asyncio
async def test_ignores_own_messages(mock_client, mock_message):
    """Bot should ignore its own messages."""
    mock_message.author = mock_client.user

    with patch('bot.client', mock_client):
        await on_message(mock_message)

    mock_message.channel.send.assert_not_called()


@pytest.mark.asyncio
async def test_ignores_messages_without_mention(mock_client, mock_message):
    """Bot should ignore messages that don't mention it."""
    mock_message.content = "Hello everyone!"
    mock_message.mentions = []

    with patch('bot.client', mock_client):
        await on_message(mock_message)

    mock_message.channel.send.assert_not_called()


@pytest.mark.asyncio
async def test_responds_to_mention(mock_client, mock_message, monkeypatch):
    """Bot should respond when mentioned with question."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')

    # Reset config singleton
    import config
    config._settings = None

    from datetime import datetime, timezone
    mock_message.content = f"<@{mock_client.user.id}> What did we discuss?"
    mock_message.mentions = [mock_client.user]
    mock_message.created_at = datetime.now(timezone.utc)

    with patch('bot.client', mock_client), \
         patch('bot.run_agent', new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = ("Here's what I found...", [])

        await on_message(mock_message)

    assert mock_agent.called
    assert mock_message.channel.send.called


@pytest.mark.asyncio
async def test_handles_empty_question(mock_client, mock_message, monkeypatch):
    """Bot should infer question from recent messages if mention has no text."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')

    # Reset config singleton
    import config
    config._settings = None

    from datetime import datetime, timezone
    mock_message.content = f"<@{mock_client.user.id}>"
    mock_message.mentions = [mock_client.user]
    mock_message.created_at = datetime.now(timezone.utc)

    with patch('bot.client', mock_client), \
         patch('bot.run_agent', new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = ("Based on recent messages, here's what I found...", [])

        await on_message(mock_message)

    # Should call agent with inference question
    assert mock_agent.called
    call_args = mock_agent.call_args
    # call_args is a tuple of (args, kwargs)
    args = call_args[0] if call_args else ()
    if args:
        question = args[0]  # First positional argument
        assert "infer" in question.lower() or "recent messages" in question.lower()
    assert mock_message.channel.send.called


@pytest.mark.asyncio
async def test_send_chunked_response_single_chunk(monkeypatch):
    """Should send single message if under limit."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    monkeypatch.setenv('MAX_RESPONSE_LENGTH', '2000')

    channel = Mock(spec=discord.TextChannel)
    channel.send = AsyncMock()

    await send_chunked_response(channel, "Short response")

    assert channel.send.call_count == 1


@pytest.mark.asyncio
async def test_send_chunked_response_multiple_chunks(monkeypatch):
    """Should send multiple messages if over limit."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    monkeypatch.setenv('MAX_RESPONSE_LENGTH', '2000')

    channel = Mock(spec=discord.TextChannel)
    channel.send = AsyncMock()

    long_text = "A" * 3000

    await send_chunked_response(channel, long_text)

    assert channel.send.call_count == 2


@pytest.mark.asyncio
async def test_send_error_message_to_channel(monkeypatch):
    """Should send error to channel."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')

    message = Mock(spec=discord.Message)
    message.channel = Mock(spec=discord.TextChannel)
    message.channel.send = AsyncMock()

    await send_error_message(message, "something went wrong")

    message.channel.send.assert_called_once()
    assert "sorry" in message.channel.send.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_send_error_message_to_debug_channel(monkeypatch):
    """Should send detailed error to debug channel if configured."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    monkeypatch.setenv('DEBUG_CHANNEL_NAME', 'debug')

    # Reset config singleton to pick up new env vars
    import config
    config._settings = None

    debug_channel = Mock(spec=discord.TextChannel)
    debug_channel.send = AsyncMock()
    debug_channel.name = 'debug'

    guild = Mock(spec=discord.Guild)
    guild.text_channels = [debug_channel]

    message = Mock(spec=discord.Message)
    message.channel = Mock(spec=discord.TextChannel)
    message.channel.send = AsyncMock()
    message.channel.mention = "#general"
    message.channel.guild = guild

    with patch('bot.client', Mock()):
        await send_error_message(
            message,
            "something went wrong",
            log_error="Detailed error info"
        )

    assert debug_channel.send.called


@patch('bot.initialize_instrumentation')
@patch('bot.get_settings')
@patch('bot.client')
def test_main_initializes_instrumentation(mock_client, mock_get_settings, mock_init_instrumentation):
    """Test that main() initializes instrumentation before starting bot."""
    mock_settings = MagicMock()
    mock_settings.discord_token = "test_token"
    mock_get_settings.return_value = mock_settings
    mock_client.run = Mock()

    main()

    # Verify instrumentation was initialized
    mock_init_instrumentation.assert_called_once_with(mock_settings)

    # Verify bot was started after instrumentation
    mock_client.run.assert_called_once_with("test_token")
