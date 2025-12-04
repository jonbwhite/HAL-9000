# Discord Bot Implementation Plan

## Overview

This plan guides implementation of a Discord bot that answers questions about channel message history using AI. The bot uses pydanticai with Claude to intelligently fetch and analyze Discord messages.

**Core Technologies:**
- discord.py: Discord API integration
- pydanticai: AI agent framework with tool calling
- Anthropic Claude: LLM provider
- pydantic-settings: Type-safe configuration

## Architecture Summary

1. User mentions bot with question
2. Bot extracts question, shows typing indicator
3. PydanticAI agent receives question and context
4. Agent calls tools to fetch Discord messages
5. Agent processes messages and generates response
6. Bot streams response back, chunking if needed

## Prerequisites

**APIs & Tokens Needed:**
- Discord Bot Token: Create at https://discord.com/developers/applications
  - Enable "Message Content Intent" in Bot settings
  - Invite bot to test server with permissions: Read Messages, Send Messages, Read Message History
- Anthropic API Key: Get from https://console.anthropic.com/

**Documentation to Reference:**
- discord.py: https://discordpy.readthedocs.io/
- pydanticai: https://ai.pydantic.dev/
- pydantic-settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

## Project Structure

```
discord-bot/
├── bot.py           # Discord client and message handling
├── agent.py         # PydanticAI agent configuration
├── tools.py         # Tool definitions for agent
├── config.py        # Settings with pydantic-settings
├── utils.py         # Helper functions (chunking, etc.)
├── tests/
│   ├── test_config.py
│   ├── test_tools.py
│   ├── test_agent.py
│   ├── test_utils.py
│   └── test_bot.py
├── .env.example     # Already exists
├── .env             # Created by developer (not in git)
└── pyproject.toml   # Already exists
```

---

## Task Breakdown

### Task 1: Set up configuration with pydantic-settings

**Goal:** Create type-safe configuration management

**Files to create:**
- `config.py`

**Implementation:**

```python
# ABOUTME: Application configuration using pydantic-settings
# ABOUTME: Loads settings from environment variables and .env file

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required settings
    discord_token: str
    anthropic_api_key: str

    # Optional settings with defaults
    debug_channel_id: Optional[int] = None
    default_message_limit: int = 100
    default_time_window_hours: int = 24
    max_response_length: int = 2000

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False
    )


# Singleton instance
settings = Settings()
```

**Update `.env.example`:**

```
DISCORD_TOKEN=your_discord_bot_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DEBUG_CHANNEL_ID=1234567890
DEFAULT_MESSAGE_LIMIT=100
DEFAULT_TIME_WINDOW_HOURS=24
MAX_RESPONSE_LENGTH=2000
```

**Create your `.env` file:**
Copy `.env.example` to `.env` and fill in your actual tokens.

**Files to create for testing:**
- `tests/test_config.py`

**Test implementation:**

```python
# ABOUTME: Tests for configuration management
# ABOUTME: Validates settings loading and validation

import pytest
from pydantic import ValidationError
from config import Settings
import os


def test_settings_requires_discord_token(monkeypatch):
    """Settings should raise error if DISCORD_TOKEN missing."""
    monkeypatch.delenv('DISCORD_TOKEN', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert 'discord_token' in str(exc_info.value)


def test_settings_requires_anthropic_key(monkeypatch):
    """Settings should raise error if ANTHROPIC_API_KEY missing."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert 'anthropic_api_key' in str(exc_info.value)


def test_settings_loads_with_required_fields(monkeypatch):
    """Settings should load successfully with required fields."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_discord_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_anthropic_key')

    settings = Settings()

    assert settings.discord_token == 'test_discord_token'
    assert settings.anthropic_api_key == 'test_anthropic_key'
    assert settings.default_message_limit == 100
    assert settings.default_time_window_hours == 24


def test_settings_uses_custom_values(monkeypatch):
    """Settings should use custom values when provided."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    monkeypatch.setenv('DEFAULT_MESSAGE_LIMIT', '50')
    monkeypatch.setenv('DEBUG_CHANNEL_ID', '123456')

    settings = Settings()

    assert settings.default_message_limit == 50
    assert settings.debug_channel_id == 123456
```

**How to run tests:**
```bash
poetry add --group dev pytest
poetry run pytest tests/test_config.py -v
```

**Commit point:**
```bash
git add config.py tests/test_config.py .env.example
git commit -m "Add configuration management with pydantic-settings

- Create Settings class with required and optional fields
- Add comprehensive tests for configuration loading
- Update .env.example with all configuration options"
```

---

### Task 2: Create utility functions

**Goal:** Build helper functions for message chunking and time parsing

**Files to create:**
- `utils.py`

**Implementation:**

```python
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
    return datetime.utcnow() - timedelta(hours=hours)
```

**Files to create for testing:**
- `tests/test_utils.py`

**Test implementation:**

```python
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
    before = datetime.utcnow()
    window = get_time_window(24)
    after = datetime.utcnow()

    expected_min = before - timedelta(hours=24, seconds=1)
    expected_max = after - timedelta(hours=24)

    assert expected_min <= window <= expected_max
```

**How to run tests:**
```bash
poetry run pytest tests/test_utils.py -v
```

**Commit point:**
```bash
git add utils.py tests/test_utils.py
git commit -m "Add utility functions for message chunking and time windows

- Implement intelligent message chunking at paragraph/sentence boundaries
- Add time window calculation for message history
- Add comprehensive tests for edge cases"
```

---

### Task 3: Create Discord message fetching tool

**Goal:** Implement the tool that the AI agent will use to fetch Discord messages

**Files to create:**
- `tools.py`

**Implementation:**

```python
# ABOUTME: Tool definitions for pydanticai agent
# ABOUTME: Provides message fetching capability from Discord channels

from datetime import datetime
from typing import List, Optional
import discord
from pydantic import BaseModel, Field
from utils import get_time_window
from config import settings


class MessageData(BaseModel):
    """Structured representation of a Discord message."""
    author: str
    timestamp: datetime
    content: str

    def __str__(self) -> str:
        """Format message for display to AI."""
        time_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"[{time_str}] {self.author}: {self.content}"


class FetchMessagesParams(BaseModel):
    """Parameters for fetch_messages tool."""
    channel_id: int = Field(description="Discord channel ID to fetch messages from")
    hours_back: int = Field(
        default=24,
        description="How many hours of message history to fetch",
        ge=1,
        le=168  # Max 1 week
    )
    limit: Optional[int] = Field(
        default=None,
        description="Maximum number of messages to fetch (None for config default)",
        ge=1,
        le=500
    )


async def fetch_messages_tool(
    params: FetchMessagesParams,
    client: discord.Client
) -> List[MessageData]:
    """
    Fetch messages from a Discord channel within a time window.

    This tool is called by the AI agent to retrieve message history.

    Args:
        params: Parameters including channel_id, hours_back, limit
        client: Discord client instance

    Returns:
        List of MessageData objects with author, timestamp, content

    Raises:
        ValueError: If channel not found or not accessible
    """
    channel = client.get_channel(params.channel_id)

    if not channel:
        raise ValueError(f"Channel {params.channel_id} not found or not accessible")

    if not isinstance(channel, discord.TextChannel):
        raise ValueError(f"Channel {params.channel_id} is not a text channel")

    # Calculate time window
    after_time = get_time_window(params.hours_back)

    # Fetch messages
    limit = params.limit or settings.default_message_limit
    messages = []

    async for message in channel.history(
        limit=limit,
        after=after_time,
        oldest_first=False
    ):
        # Skip bot messages to reduce noise
        if not message.author.bot:
            messages.append(MessageData(
                author=message.author.display_name,
                timestamp=message.created_at,
                content=message.content
            ))

    # Return in chronological order (oldest first)
    return list(reversed(messages))
```

**Files to create for testing:**
- `tests/test_tools.py`

**Test implementation:**

```python
# ABOUTME: Tests for Discord message fetching tools
# ABOUTME: Uses mocked Discord API to test tool functionality

import pytest
from datetime import datetime, timedelta
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
    base_time = datetime.utcnow() - timedelta(hours=2)

    for i in range(5):
        msg = Mock(spec=discord.Message)
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
        msg.author.display_name = f"User{i}"
        msg.author.bot = i == 1  # Middle message is from bot
        msg.content = f"Message {i}"
        msg.created_at = datetime.utcnow()
        messages.append(msg)

    mock_discord_client.get_channel.return_value = mock_text_channel

    async def async_generator():
        for msg in messages:
            yield msg

    mock_text_channel.history.return_value = async_generator()

    params = FetchMessagesParams(channel_id=123456, hours_back=24)
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
```

**How to run tests:**
```bash
poetry run pytest tests/test_tools.py -v
```

**Commit point:**
```bash
git add tools.py tests/test_tools.py
git commit -m "Add Discord message fetching tool for AI agent

- Implement fetch_messages_tool with time window support
- Add structured MessageData model
- Filter out bot messages from results
- Add comprehensive tests with mocked Discord API"
```

---

### Task 4: Create pydanticai agent

**Goal:** Set up the AI agent that will process questions and call tools

**Files to create:**
- `agent.py`

**Implementation:**

```python
# ABOUTME: PydanticAI agent configuration
# ABOUTME: Sets up Claude agent with message fetching capabilities

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic import BaseModel
from typing import List
import discord
from config import settings
from tools import fetch_messages_tool, FetchMessagesParams, MessageData


class AgentContext(BaseModel):
    """Context provided to the agent for each query."""
    question: str
    channel_id: int
    channel_name: str
    user_name: str
    guild_name: str


class AgentDependencies(BaseModel):
    """Dependencies injected into agent tools."""
    discord_client: discord.Client

    class Config:
        arbitrary_types_allowed = True


# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful productivity assistant for a Discord server.

Your role is to answer questions about messages in Discord channels. You have access to a tool
that can fetch message history from channels.

When a user asks a question:
1. Determine if you need to fetch messages to answer it
2. Use the fetch_messages tool with appropriate parameters (channel_id, hours_back, limit)
3. Analyze the messages and provide a clear, concise answer
4. If the messages don't contain relevant information, say so clearly

Guidelines:
- Be helpful and conversational
- Cite specific messages when relevant (e.g., "User X mentioned...")
- If asked about timeframes, adjust the hours_back parameter accordingly
- Default to the current channel unless the user specifies another
- Keep responses focused and relevant to the question"""


# Create the agent
productivity_agent = Agent(
    model=AnthropicModel(
        model_name='claude-3-5-sonnet-20241022',
        api_key=settings.anthropic_api_key
    ),
    system_prompt=SYSTEM_PROMPT,
    deps_type=AgentDependencies
)


@productivity_agent.tool
async def fetch_messages(
    ctx: AgentContext,
    deps: AgentDependencies,
    channel_id: int,
    hours_back: int = 24,
    limit: int | None = None
) -> List[MessageData]:
    """
    Fetch messages from a Discord channel.

    Args:
        channel_id: The Discord channel ID to fetch from
        hours_back: How many hours of history to fetch (1-168)
        limit: Maximum messages to fetch (default from config)

    Returns:
        List of messages with author, timestamp, and content
    """
    params = FetchMessagesParams(
        channel_id=channel_id,
        hours_back=hours_back,
        limit=limit
    )
    return await fetch_messages_tool(params, deps.discord_client)


async def run_agent(
    question: str,
    channel: discord.TextChannel,
    user: discord.User,
    discord_client: discord.Client
) -> str:
    """
    Run the productivity agent with a user's question.

    Args:
        question: The user's question
        channel: Discord channel where question was asked
        user: Discord user who asked
        discord_client: Discord client for fetching messages

    Returns:
        Agent's response as a string
    """
    context = AgentContext(
        question=question,
        channel_id=channel.id,
        channel_name=channel.name,
        user_name=user.display_name,
        guild_name=channel.guild.name
    )

    dependencies = AgentDependencies(discord_client=discord_client)

    result = await productivity_agent.run(
        question,
        deps=dependencies,
        message_history=[]
    )

    return result.data
```

**Files to create for testing:**
- `tests/test_agent.py`

**Test implementation:**

```python
# ABOUTME: Tests for pydanticai agent
# ABOUTME: Validates agent setup and tool integration (mocked)

import pytest
from unittest.mock import Mock, AsyncMock, patch
import discord
from datetime import datetime
from agent import run_agent, AgentContext, AgentDependencies
from tools import MessageData


@pytest.fixture
def mock_discord_objects():
    """Create mocked Discord objects for testing."""
    client = Mock(spec=discord.Client)

    guild = Mock(spec=discord.Guild)
    guild.name = "Test Server"

    channel = Mock(spec=discord.TextChannel)
    channel.id = 123456789
    channel.name = "general"
    channel.guild = guild

    user = Mock(spec=discord.User)
    user.display_name = "TestUser"

    return client, channel, user


@pytest.mark.asyncio
async def test_agent_context_creation(mock_discord_objects):
    """Agent context should be created with correct fields."""
    _, channel, user = mock_discord_objects

    context = AgentContext(
        question="What did we discuss?",
        channel_id=channel.id,
        channel_name=channel.name,
        user_name=user.display_name,
        guild_name=channel.guild.name
    )

    assert context.question == "What did we discuss?"
    assert context.channel_id == 123456789
    assert context.channel_name == "general"
    assert context.user_name == "TestUser"
    assert context.guild_name == "Test Server"


@pytest.mark.asyncio
async def test_agent_dependencies_accepts_client(mock_discord_objects):
    """Agent dependencies should accept Discord client."""
    client, _, _ = mock_discord_objects

    deps = AgentDependencies(discord_client=client)

    assert deps.discord_client == client


# Note: Full integration test with real API would be expensive
# In practice, you'd mock the agent.run() call or test with recorded responses
@pytest.mark.asyncio
@patch('agent.productivity_agent.run')
async def test_run_agent_calls_agent_correctly(mock_agent_run, mock_discord_objects):
    """run_agent should call pydanticai agent with correct parameters."""
    client, channel, user = mock_discord_objects

    # Mock the agent response
    mock_result = Mock()
    mock_result.data = "Here's what I found..."
    mock_agent_run.return_value = mock_result

    question = "What did we discuss about the project?"
    response = await run_agent(question, channel, user, client)

    assert response == "Here's what I found..."
    assert mock_agent_run.called

    # Verify the agent was called with the question
    call_args = mock_agent_run.call_args
    assert question in call_args[0]
```

**How to run tests:**
```bash
poetry run pytest tests/test_agent.py -v
```

**Note on testing:** Full end-to-end testing of the agent with real API calls would be expensive. The tests above validate the setup and integration points. For deeper testing, you could:
- Use pydanticai's testing utilities (if available)
- Record and replay agent responses
- Test with a cheaper/faster model in test environment

**Commit point:**
```bash
git add agent.py tests/test_agent.py
git commit -m "Add pydanticai agent with Claude and tool support

- Configure agent with Anthropic Claude model
- Register fetch_messages tool for agent use
- Add run_agent helper for Discord integration
- Include system prompt for productivity assistance
- Add basic agent tests with mocked responses"
```

---

### Task 5: Implement Discord bot message handling

**Goal:** Create the Discord bot that listens for mentions and processes questions

**Files to modify:**
- `bot.py`

**Implementation:**

Replace the existing `bot.py` with:

```python
# ABOUTME: Discord bot entry point
# ABOUTME: Handles message events and coordinates with AI agent

import os
import asyncio
from typing import Optional
import discord
from discord import Message
from config import settings
from agent import run_agent
from utils import chunk_message

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    """Called when bot successfully connects to Discord."""
    print(f'{client.user} has connected to Discord!')
    print(f'Bot is in {len(client.guilds)} guilds')


async def send_error_message(
    message: Message,
    error_text: str,
    log_error: Optional[str] = None
):
    """
    Send user-friendly error message and optionally log to debug channel.

    Args:
        message: Original Discord message
        error_text: User-friendly error message
        log_error: Detailed error for debug channel
    """
    await message.channel.send(f"Sorry, {error_text}")

    if log_error and settings.debug_channel_id:
        debug_channel = client.get_channel(settings.debug_channel_id)
        if debug_channel:
            await debug_channel.send(f"Error in {message.channel.mention}:\n```\n{log_error}\n```")


async def send_chunked_response(channel: discord.TextChannel, response: str):
    """
    Send response to Discord, chunking if necessary.

    Args:
        channel: Channel to send to
        response: Response text to send
    """
    chunks = chunk_message(response, max_length=settings.max_response_length)

    for chunk in chunks:
        await channel.send(chunk)


@client.event
async def on_message(message: Message):
    """
    Handle incoming Discord messages.

    Responds when bot is mentioned with a question.
    """
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Check if bot is mentioned
    if client.user not in message.mentions:
        return

    # Extract question (remove bot mention)
    question = message.content
    for mention in message.mentions:
        question = question.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
    question = question.strip()

    if not question:
        await message.channel.send("Please ask me a question!")
        return

    # Verify we're in a text channel
    if not isinstance(message.channel, discord.TextChannel):
        await message.channel.send("I can only answer questions in text channels.")
        return

    # Show typing indicator while processing
    async with message.channel.typing():
        try:
            # Run the AI agent
            response = await run_agent(
                question=question,
                channel=message.channel,
                user=message.author,
                discord_client=client
            )

            # Send response (chunked if needed)
            await send_chunked_response(message.channel, response)

        except ValueError as e:
            # User-facing errors (channel not found, etc.)
            await send_error_message(
                message,
                error_text=str(e),
                log_error=f"ValueError: {e}\nQuestion: {question}\nUser: {message.author}"
            )

        except Exception as e:
            # Unexpected errors
            error_msg = f"I encountered an error processing your question."
            log_msg = f"Unexpected error:\n{type(e).__name__}: {e}\nQuestion: {question}\nUser: {message.author}"

            await send_error_message(
                message,
                error_text=error_msg,
                log_error=log_msg
            )

            # Also print to console for local debugging
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Start the Discord bot."""
    token = settings.discord_token
    if not token:
        raise ValueError('DISCORD_TOKEN not found in environment variables')

    print("Starting Discord bot...")
    client.run(token)


if __name__ == '__main__':
    main()
```

**Files to create for testing:**
- `tests/test_bot.py`

**Test implementation:**

```python
# ABOUTME: Tests for Discord bot message handling
# ABOUTME: Validates mention detection, error handling, response chunking

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import discord
from bot import on_message, send_error_message, send_chunked_response


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
    message.channel = Mock(spec=discord.TextChannel)
    message.channel.send = AsyncMock()
    message.channel.typing = MagicMock()
    message.mentions = []
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
async def test_responds_to_mention(mock_client, mock_message):
    """Bot should respond when mentioned with question."""
    mock_message.content = f"<@{mock_client.user.id}> What did we discuss?"
    mock_message.mentions = [mock_client.user]

    with patch('bot.client', mock_client), \
         patch('bot.run_agent', new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = "Here's what I found..."

        await on_message(mock_message)

    assert mock_agent.called
    assert mock_message.channel.send.called


@pytest.mark.asyncio
async def test_handles_empty_question(mock_client, mock_message):
    """Bot should prompt for question if mention has no text."""
    mock_message.content = f"<@{mock_client.user.id}>"
    mock_message.mentions = [mock_client.user]

    with patch('bot.client', mock_client):
        await on_message(mock_message)

    mock_message.channel.send.assert_called_once()
    call_args = mock_message.channel.send.call_args[0][0]
    assert "ask me a question" in call_args.lower()


@pytest.mark.asyncio
async def test_send_chunked_response_single_chunk():
    """Should send single message if under limit."""
    channel = Mock(spec=discord.TextChannel)
    channel.send = AsyncMock()

    with patch('bot.settings.max_response_length', 2000):
        await send_chunked_response(channel, "Short response")

    assert channel.send.call_count == 1


@pytest.mark.asyncio
async def test_send_chunked_response_multiple_chunks():
    """Should send multiple messages if over limit."""
    channel = Mock(spec=discord.TextChannel)
    channel.send = AsyncMock()

    long_text = "A" * 3000

    with patch('bot.settings.max_response_length', 2000):
        await send_chunked_response(channel, long_text)

    assert channel.send.call_count == 2


@pytest.mark.asyncio
async def test_send_error_message_to_channel():
    """Should send error to channel."""
    message = Mock(spec=discord.Message)
    message.channel = Mock(spec=discord.TextChannel)
    message.channel.send = AsyncMock()

    with patch('bot.settings.debug_channel_id', None):
        await send_error_message(message, "something went wrong")

    message.channel.send.assert_called_once()
    assert "sorry" in message.channel.send.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_send_error_message_to_debug_channel():
    """Should send detailed error to debug channel if configured."""
    message = Mock(spec=discord.Message)
    message.channel = Mock(spec=discord.TextChannel)
    message.channel.send = AsyncMock()
    message.channel.mention = "#general"

    debug_channel = Mock(spec=discord.TextChannel)
    debug_channel.send = AsyncMock()

    mock_client = Mock()
    mock_client.get_channel.return_value = debug_channel

    with patch('bot.settings.debug_channel_id', 123456), \
         patch('bot.client', mock_client):
        await send_error_message(
            message,
            "something went wrong",
            log_error="Detailed error info"
        )

    assert debug_channel.send.called
```

**How to run tests:**
```bash
poetry run pytest tests/test_bot.py -v
```

**Manual testing:**
1. Set up your `.env` file with real tokens
2. Run the bot: `poetry run python bot.py`
3. In Discord, mention the bot: `@YourBot what messages were sent in the last hour?`
4. Verify it responds appropriately

**Commit point:**
```bash
git add bot.py tests/test_bot.py
git commit -m "Implement Discord bot mention handling and agent integration

- Handle bot mentions and extract questions
- Integrate with pydanticai agent for processing
- Add typing indicator during processing
- Implement chunked responses for long messages
- Add error handling with user-friendly messages
- Support debug channel for error logging
- Add comprehensive tests for message handling"
```

---

### Task 6: Add development dependencies and test runner

**Goal:** Set up proper testing infrastructure

**Commands to run:**

```bash
# Add development dependencies
poetry add --group dev pytest pytest-asyncio pytest-mock

# Create pytest configuration
```

**Files to create:**
- `pytest.ini`

**Implementation:**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
```

**How to run all tests:**
```bash
# Run all tests
poetry run pytest -v

# Run with coverage
poetry add --group dev pytest-cov
poetry run pytest --cov=. --cov-report=html

# Run specific test file
poetry run pytest tests/test_agent.py -v

# Run tests matching pattern
poetry run pytest -k "test_fetch" -v
```

**Commit point:**
```bash
git add pytest.ini pyproject.toml poetry.lock
git commit -m "Add testing infrastructure

- Add pytest, pytest-asyncio, pytest-mock
- Configure pytest with asyncio support
- Add pytest-cov for coverage reporting"
```

---

### Task 7: Add documentation and setup guide

**Goal:** Document how to set up and run the bot

**Files to update:**
- `README.md`

**Implementation:**

Replace existing README.md:

```markdown
# Discord Productivity Bot

An AI-powered Discord bot that answers questions about channel message history using Claude.

## Features

- **Question Answering**: Ask the bot questions about past discussions in channels
- **Intelligent Tool Use**: Uses pydanticai agents that intelligently fetch relevant message history
- **Natural Interaction**: Simply mention the bot with your question
- **Smart Chunking**: Handles long responses by splitting at natural boundaries
- **Error Handling**: User-friendly error messages with optional debug logging

## Architecture

- **Discord.py**: Discord API integration and event handling
- **PydanticAI**: AI agent framework with tool calling capabilities
- **Anthropic Claude**: LLM for understanding questions and generating responses
- **Pydantic Settings**: Type-safe configuration management

## Setup

### Prerequisites

1. **Discord Bot Token**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to Bot section and create a bot
   - Enable "Message Content Intent" under Privileged Gateway Intents
   - Copy the token

2. **Invite Bot to Server**
   - In Developer Portal, go to OAuth2 > URL Generator
   - Select scopes: `bot`
   - Select permissions: `Read Messages`, `Send Messages`, `Read Message History`
   - Use generated URL to invite bot to your server

3. **Anthropic API Key**
   - Sign up at [Anthropic Console](https://console.anthropic.com/)
   - Generate an API key

### Installation

1. **Clone and enter directory**
   ```bash
   cd discord-bot
   ```

2. **Install Python dependencies**
   ```bash
   poetry install
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your tokens
   ```

   Required variables:
   - `DISCORD_TOKEN`: Your Discord bot token
   - `ANTHROPIC_API_KEY`: Your Anthropic API key

   Optional variables:
   - `DEBUG_CHANNEL_ID`: Discord channel ID for error logging
   - `DEFAULT_MESSAGE_LIMIT`: Max messages to fetch (default: 100)
   - `DEFAULT_TIME_WINDOW_HOURS`: Default hours to look back (default: 24)
   - `MAX_RESPONSE_LENGTH`: Max message length before chunking (default: 2000)

### Running

```bash
poetry run python bot.py
```

## Usage

Mention the bot in any channel with a question:

```
@BotName what did we discuss about the deployment?
@BotName summarize today's conversation
@BotName who mentioned the bug fix?
```

The bot will:
1. Show a typing indicator
2. Use AI to determine what message history to fetch
3. Analyze the messages
4. Respond with an answer

## Development

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=. --cov-report=html

# Run specific test file
poetry run pytest tests/test_agent.py -v
```

### Project Structure

```
discord-bot/
├── bot.py           # Discord client and message handling
├── agent.py         # PydanticAI agent configuration
├── tools.py         # Tool definitions for fetching messages
├── config.py        # Settings with pydantic-settings
├── utils.py         # Helper functions
├── tests/           # Test suite
│   ├── test_bot.py
│   ├── test_agent.py
│   ├── test_tools.py
│   ├── test_config.py
│   └── test_utils.py
└── docs/
    └── plans/       # Implementation plans
```

### Adding New Tools

To add new capabilities:

1. Define tool function in `tools.py`
2. Register tool with agent in `agent.py` using `@productivity_agent.tool`
3. Update system prompt if needed
4. Add tests in `tests/test_tools.py`

Example:

```python
# In tools.py
async def search_messages_tool(query: str, client: discord.Client):
    # Implementation
    pass

# In agent.py
@productivity_agent.tool
async def search_messages(ctx: AgentContext, deps: AgentDependencies, query: str):
    return await search_messages_tool(query, deps.discord_client)
```

## Troubleshooting

### Bot doesn't respond to mentions

- Verify "Message Content Intent" is enabled in Discord Developer Portal
- Check bot has permissions in the channel
- Verify bot is actually online (check on_ready message in console)

### API errors

- Check API keys are correct in `.env`
- Verify you have API credits (Anthropic)
- Check console for detailed error messages

### Import errors

- Run `poetry install` to ensure all dependencies are installed
- Verify you're using correct Python version (3.13+)

## License

MIT
```

**Commit point:**
```bash
git add README.md
git commit -m "Update README with comprehensive setup and usage docs

- Add detailed setup instructions for Discord and Anthropic
- Document bot usage and features
- Add development and testing guide
- Include troubleshooting section"
```

---

## Summary of Implementation

After completing all tasks, you will have:

✅ Type-safe configuration with pydantic-settings
✅ Discord message fetching tool with time windows
✅ PydanticAI agent integrated with Claude
✅ Discord bot that responds to mentions
✅ Intelligent message chunking
✅ Error handling with debug logging
✅ Comprehensive test suite
✅ Complete documentation

### Final Verification

1. **Run all tests:**
   ```bash
   poetry run pytest -v
   ```
   All tests should pass.

2. **Test the bot manually:**
   - Start bot: `poetry run python bot.py`
   - Mention it in Discord with a question
   - Verify it responds appropriately

3. **Check test coverage:**
   ```bash
   poetry run pytest --cov=. --cov-report=term
   ```
   Aim for >80% coverage.

### Next Steps

After completing this implementation:

1. **Add more tools** as needed (search, user info, etc.)
2. **Improve system prompt** based on real usage
3. **Add conversation history** for multi-turn interactions
4. **Implement rate limiting** to prevent abuse
5. **Add monitoring/logging** for production use
6. **Deploy to cloud** (Railway, Heroku, etc.)

### Deployment Considerations

When deploying to production:

- Use environment variables for all secrets (never commit `.env`)
- Set up proper logging
- Consider rate limiting per user
- Monitor API costs (Anthropic usage)
- Set up health checks
- Use process manager (systemd, pm2) or containerize with Docker

---

## Appendix: Key Design Decisions

### Why PydanticAI?

- Native tool calling support
- Type-safe agent configuration
- Good integration with pydantic ecosystem
- Flexible model providers

### Why Mention-Based Interaction?

- Natural and discoverable
- No slash command registration needed
- Works in any channel
- Clear attribution of questions

### Why Chunk at Paragraph/Sentence Boundaries?

- Better reading experience
- Preserves semantic units
- Avoids splitting mid-thought

### Why Filter Bot Messages?

- Reduces noise in results
- Prevents recursive bot conversations
- Focuses on human discussions

### Why Optional Debug Channel?

- Keeps error details out of public channels
- Helps debugging in production
- Respects user experience
