# ABOUTME: Tool definitions for pydanticai agent
# ABOUTME: Provides message fetching capability from Discord channels

from datetime import datetime
from typing import List, Optional
import discord
from pydantic import BaseModel, Field
from utils import get_time_window
from config import get_settings


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
    limit = params.limit or get_settings().default_message_limit
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
