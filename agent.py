# ABOUTME: PydanticAI agent configuration
# ABOUTME: Sets up Claude agent with message fetching capabilities

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime, timedelta, UTC
import discord
from config import get_settings
from tools import fetch_messages_tool, FetchMessagesParams, MessageData


class AgentContext(BaseModel):
    """Context provided to the agent for each query."""
    question: str
    channel_id: int
    channel_name: str
    server_id: int
    server_name: str
    user_name: str
    recent_messages: Optional[List[MessageData]] = None


class AgentDependencies(BaseModel):
    """Dependencies injected into agent tools."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    discord_client: discord.Client


# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful productivity assistant for a Discord server.

Your role is to answer questions about messages in Discord channels. You have access to tools
that can fetch message history from channels and resolve channel names to IDs.

Recent messages from the current channel are automatically provided in the context (recent_messages field).
This allows you to answer follow-up questions and maintain conversation context without needing to fetch messages.

When a user asks a question:
1. Check if the recent_messages in context contain relevant information
2. If you need more history or messages from other channels, use the fetch_messages tool
3. If the user mentions a channel by name, use the get_channel_id tool to resolve it
4. Use the fetch_messages tool with appropriate parameters (channel_id, hours_back, limit) when needed
5. Analyze the messages and provide a clear, concise answer
6. If the messages don't contain relevant information, say so clearly

Guidelines:
- Be helpful and conversational
- Use the recent_messages context when available to answer follow-up questions
- Cite specific messages when relevant (e.g., "User X mentioned...")
- If asked about timeframes, adjust the hours_back parameter accordingly
- Users think in terms of channel names, not channel IDs
- Default to the context channel (channel_id and channel_name are provided in context) unless the user specifies another
- When a user specifies a different channel by name, use get_channel_id with the channel_name and server_id from context
- Keep responses focused and relevant to the question"""


def create_productivity_agent() -> Agent:
    """Create and return the productivity agent instance."""
    settings = get_settings()

    provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    agent = Agent(
        model=AnthropicModel(
            model_name='claude-sonnet-4-5-20250929',
            provider=provider
        ),
        system_prompt=SYSTEM_PROMPT,
        deps_type=AgentDependencies
    )

    @agent.tool
    async def get_channel_id(
        ctx: RunContext[AgentDependencies],
        channel_name: str,
        server_id: int
    ) -> int:
        """
        Resolve a channel name to a channel ID within a server.

        Args:
            channel_name: The name of the channel to find (case-insensitive)
            server_id: The server ID to search within (from context)

        Returns:
            The channel ID as an integer

        Raises:
            ValueError: If channel not found or server not accessible
        """
        guild = ctx.deps.discord_client.get_guild(server_id)
        if not guild:
            raise ValueError(f"Server {server_id} not found or not accessible")

        # Search for channel with case-insensitive matching
        channel = None
        for ch in guild.channels:
            if isinstance(ch, discord.TextChannel) and ch.name.lower() == channel_name.lower():
                channel = ch
                break

        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found in server")

        return channel.id

    @agent.tool
    async def fetch_messages(
        ctx: RunContext[AgentDependencies],
        channel_id: int,
        hours_back: int = 24,
        limit: int | None = None
    ) -> List[MessageData]:
        """
        Fetch messages from a Discord channel.

        Args:
            channel_id: The Discord channel ID to fetch from (can be obtained from get_channel_id or from context)
            hours_back: How many hours of history to fetch (1-168)
            limit: Maximum messages to fetch (default from config)

        Returns:
            List of messages with author, timestamp, and content

        Note:
            Default to the context channel_id unless the user specifies another channel.
            If the user specifies a channel by name, use get_channel_id first to resolve it.
        """
        params = FetchMessagesParams(
            channel_id=channel_id,
            hours_back=hours_back,
            limit=limit
        )
        return await fetch_messages_tool(params, ctx.deps.discord_client)

    return agent


async def fetch_recent_messages(
    channel: discord.TextChannel,
    minutes_back: int,
    limit: int
) -> List[MessageData]:
    """
    Fetch recent messages from a Discord channel for automatic context.

    Args:
        channel: Discord text channel to fetch from
        minutes_back: How many minutes of history to fetch
        limit: Maximum number of messages to return

    Returns:
        List of MessageData objects in chronological order (oldest first).
        Returns empty list on any errors (graceful degradation).
    """
    try:
        # Calculate time window
        after_time = datetime.now(UTC) - timedelta(minutes=minutes_back)

        # Fetch messages
        messages = []
        async for message in channel.history(
            limit=limit,
            after=after_time,
            oldest_first=False
        ):
            # Include all messages including bot messages
            messages.append(MessageData(
                author=message.author.display_name,
                timestamp=message.created_at,
                content=message.content
            ))

        # Return in chronological order (oldest first)
        return list(reversed(messages))
    except Exception:
        # Graceful degradation: return empty list on any error
        return []


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
    # Fetch recent messages for context
    settings = get_settings()
    recent_messages = await fetch_recent_messages(
        channel=channel,
        minutes_back=settings.recent_context_minutes,
        limit=settings.recent_context_limit
    )

    context = AgentContext(
        question=question,
        channel_id=channel.id,
        channel_name=channel.name,
        server_id=channel.guild.id,
        server_name=channel.guild.name,
        user_name=user.display_name,
        recent_messages=recent_messages if recent_messages else None,
    )

    dependencies = AgentDependencies(discord_client=discord_client)

    agent = create_productivity_agent()

    # Serialize context to JSON
    context_json = context.model_dump_json()

    result = await agent.run(
        context_json,
        deps=dependencies,
        message_history=[]
    )

    return result.output
