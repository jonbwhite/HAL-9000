# ABOUTME: Channel-based conversation tracking system
# ABOUTME: Manages active conversations per channel with timeout and response decisions

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import discord
from pydantic_ai import ModelMessage


@dataclass
class MessageRecord:
    """Lightweight representation of a Discord message."""
    author: str
    author_id: int
    content: str
    timestamp: datetime
    is_bot: bool


@dataclass
class ChannelConversation:
    """State for an active conversation in a channel."""
    channel_id: int
    started_at: datetime
    last_activity: datetime

    # All messages seen during conversation - full channel context for prompt building
    messages: list[MessageRecord] = field(default_factory=list)

    # Bot's conversation turns only (user question → bot response pairs)
    # Passed to PydanticAI's message_history for conversation continuity
    llm_history: list[ModelMessage] = field(default_factory=list)

    # Users who've participated
    participants: set[int] = field(default_factory=set)


class ConversationManager:
    """Manages active conversations per channel."""
    
    def __init__(self, timeout_seconds: int = 120):
        self.timeout = timeout_seconds
        self._conversations: dict[int, ChannelConversation] = {}

    def get(self, channel_id: int) -> Optional[ChannelConversation]:
        """
        Get active conversation for channel, or None if expired/doesn't exist.
        
        Checks timeout and returns None if conversation has expired.
        """
        conv = self._conversations.get(channel_id)
        if conv is None:
            return None
        
        # Check if expired
        now = datetime.now(timezone.utc)
        elapsed = (now - conv.last_activity).total_seconds()
        if elapsed > self.timeout:
            # Remove expired conversation
            del self._conversations[channel_id]
            return None
        
        return conv

    def start(
        self,
        channel_id: int,
        initial_messages: list[MessageRecord]
    ) -> ChannelConversation:
        """Start a new conversation in a channel."""
        now = datetime.now(timezone.utc)
        conv = ChannelConversation(
            channel_id=channel_id,
            started_at=now,
            last_activity=now,
            messages=initial_messages.copy() if initial_messages else []
        )
        
        # Add participants from initial messages
        for msg in initial_messages:
            conv.participants.add(msg.author_id)
        
        self._conversations[channel_id] = conv
        return conv

    def record_message(self, channel_id: int, message: MessageRecord):
        """
        Record a message in the conversation and bump last_activity.
        
        If no conversation exists, this does nothing (use start() first).
        """
        conv = self._conversations.get(channel_id)
        if conv is None:
            return
        
        # Update last_activity
        conv.last_activity = datetime.now(timezone.utc)
        
        # Add message
        conv.messages.append(message)
        
        # Add participant
        conv.participants.add(message.author_id)

    def record_bot_response(
        self,
        channel_id: int,
        llm_history: list[ModelMessage]
    ):
        """
        Record bot's response in the conversation's LLM history.
        
        This maintains conversation continuity for the LLM.
        """
        conv = self._conversations.get(channel_id)
        if conv is None:
            return
        
        conv.llm_history = llm_history

    def end(self, channel_id: int):
        """End a conversation in a channel."""
        self._conversations.pop(channel_id, None)


class ResponseDecider:
    """Decides when to start conversations and when to respond."""
    
    def should_start_conversation(
        self,
        message: discord.Message,
        bot_user_id: int
    ) -> tuple[bool, str]:
        """
        Should this message start a new conversation?
        
        Returns:
            Tuple of (decision, reason)
        """
        # Explicit triggers: @mention or reply to bot
        if bot_user_id in [m.id for m in message.mentions]:
            return True, "explicit_mention"
        
        if message.reference and message.reference.resolved:
            referenced = message.reference.resolved
            if isinstance(referenced, discord.Message) and referenced.author.id == bot_user_id:
                return True, "reply_to_bot"
        
        return False, "no_trigger"

    def should_respond(
        self,
        message: discord.Message,
        conversation: ChannelConversation,
        bot_user_id: int
    ) -> tuple[bool, str]:
        """
        Should bot respond to this message?
        
        Returns:
            Tuple of (decision, reason)
        """
        # For Phase 1, same logic as should_start_conversation
        return self.should_start_conversation(message, bot_user_id)
