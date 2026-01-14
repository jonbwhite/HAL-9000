# ABOUTME: Tests for pydanticai agent
# ABOUTME: Validates agent setup and tool integration (mocked)

import pytest
from unittest.mock import Mock, AsyncMock, patch
import discord
import json
from datetime import datetime
from agent import run_agent, AgentContext, AgentDependencies
from tools import MessageData
from conversation import ChannelConversation
from datetime import datetime, timezone


@pytest.fixture
def mock_discord_objects():
    """Create mocked Discord objects for testing."""
    client = Mock(spec=discord.Client)

    guild = Mock(spec=discord.Guild)
    guild.id = 987654321
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
        server_id=channel.guild.id,
        server_name=channel.guild.name,
        user_name=user.display_name,
    )

    assert context.question == "What did we discuss?"
    assert context.channel_id == 123456789
    assert context.channel_name == "general"
    assert context.server_id == 987654321
    assert context.user_name == "TestUser"
    assert context.server_name == "Test Server"
    assert context.recent_messages is None


@pytest.mark.asyncio
async def test_agent_context_with_recent_messages(mock_discord_objects):
    """Agent context should accept recent_messages field."""
    _, channel, user = mock_discord_objects

    recent_msgs = [
        MessageData(
            author="User1",
            author_id=123,
            timestamp=datetime.now(),
            content="Previous message",
            is_bot=False
        )
    ]

    context = AgentContext(
        question="What did we discuss?",
        channel_id=channel.id,
        channel_name=channel.name,
        server_id=channel.guild.id,
        server_name=channel.guild.name,
        user_name=user.display_name,
        recent_messages=recent_msgs
    )

    assert context.recent_messages == recent_msgs
    assert len(context.recent_messages) == 1


@pytest.mark.asyncio
async def test_agent_dependencies_accepts_client(mock_discord_objects):
    """Agent dependencies should accept Discord client."""
    client, _, _ = mock_discord_objects

    deps = AgentDependencies(discord_client=client)

    assert deps.discord_client == client


# Note: Full integration test with real API would be expensive
# In practice, you'd mock the agent.run() call or test with recorded responses
@pytest.mark.asyncio
@patch('agent.create_productivity_agent')
async def test_run_agent_calls_agent_correctly(mock_create_agent, mock_discord_objects, monkeypatch):
    """run_agent should call pydanticai agent with correct parameters."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    
    # Reset config singleton
    import config
    config._settings = None

    client, channel, user = mock_discord_objects

    # Create conversation with messages
    mock_recent_msgs = [
        MessageData(
            author="User1",
            author_id=123,
            timestamp=datetime.now(timezone.utc),
            content="Recent message",
            is_bot=False
        )
    ]
    conversation = ChannelConversation(
        channel_id=channel.id,
        started_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        messages=mock_recent_msgs,
        llm_history=[],
        participants=set()
    )

    # Mock the agent and its run method
    mock_agent = Mock()
    mock_result = Mock()
    mock_result.output = "Here's what I found..."
    mock_result.new_messages = Mock(return_value=[])
    mock_agent.run = AsyncMock(return_value=mock_result)
    mock_create_agent.return_value = mock_agent

    question = "What did we discuss about the project?"
    response, new_messages = await run_agent(question, channel, user, client, conversation)

    assert response == "Here's what I found..."
    assert new_messages == []
    assert mock_agent.run.called

    # Verify the agent was called with JSON context
    call_args = mock_agent.run.call_args
    context_json = call_args[0][0]
    
    # Parse and verify the JSON contains expected fields
    context_data = json.loads(context_json)
    assert context_data["question"] == question
    assert context_data["channel_id"] == 123456789
    assert context_data["channel_name"] == "general"
    assert context_data["server_id"] == 987654321
    assert context_data["user_name"] == "TestUser"
    assert context_data["server_name"] == "Test Server"
    # recent_messages should be present and contain the conversation messages
    assert "recent_messages" in context_data
    assert context_data["recent_messages"] is not None
    assert len(context_data["recent_messages"]) == 1


@pytest.mark.asyncio
@patch('agent.create_productivity_agent')
async def test_run_agent_handles_empty_conversation(mock_create_agent, mock_discord_objects, monkeypatch):
    """run_agent should work with empty conversation messages."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key')
    
    # Reset config singleton
    import config
    config._settings = None

    client, channel, user = mock_discord_objects

    # Create conversation with empty messages
    conversation = ChannelConversation(
        channel_id=channel.id,
        started_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        messages=[],
        llm_history=[],
        participants=set()
    )

    # Mock the agent and its run method
    mock_agent = Mock()
    mock_result = Mock()
    mock_result.output = "Response"
    mock_result.new_messages = Mock(return_value=[])
    mock_agent.run = AsyncMock(return_value=mock_result)
    mock_create_agent.return_value = mock_agent

    question = "Test question"
    response, new_messages = await run_agent(question, channel, user, client, conversation)

    # Should still succeed
    assert response == "Response"
    assert new_messages == []
    assert mock_agent.run.called

    # Verify context has None for recent_messages when empty
    call_args = mock_agent.run.call_args
    context_json = call_args[0][0]
    context_data = json.loads(context_json)
    assert context_data["recent_messages"] is None
