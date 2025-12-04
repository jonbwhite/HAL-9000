# ABOUTME: PydanticAI agent configuration
# ABOUTME: Sets up Claude agent with message fetching capabilities

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic import BaseModel, ConfigDict
from typing import List
import discord
from config import get_settings
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
    model_config = ConfigDict(arbitrary_types_allowed=True)

    discord_client: discord.Client


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


def create_productivity_agent() -> Agent:
    """Create and return the productivity agent instance."""
    settings = get_settings()

    agent = Agent(
        model=AnthropicModel(
            model_name='claude-3-5-sonnet-20241022',
            api_key=settings.anthropic_api_key
        ),
        system_prompt=SYSTEM_PROMPT,
        deps_type=AgentDependencies
    )

    @agent.tool
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

    return agent


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

    agent = create_productivity_agent()

    result = await agent.run(
        question,
        deps=dependencies,
        message_history=[]
    )

    return result.data
