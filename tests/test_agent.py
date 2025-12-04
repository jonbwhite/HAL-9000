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
@patch('agent.create_productivity_agent')
async def test_run_agent_calls_agent_correctly(mock_create_agent, mock_discord_objects):
    """run_agent should call pydanticai agent with correct parameters."""
    client, channel, user = mock_discord_objects

    # Mock the agent and its run method
    mock_agent = Mock()
    mock_result = Mock()
    mock_result.data = "Here's what I found..."
    mock_agent.run = AsyncMock(return_value=mock_result)
    mock_create_agent.return_value = mock_agent

    question = "What did we discuss about the project?"
    response = await run_agent(question, channel, user, client)

    assert response == "Here's what I found..."
    assert mock_agent.run.called

    # Verify the agent was called with the question
    call_args = mock_agent.run.call_args
    assert question in call_args[0]
