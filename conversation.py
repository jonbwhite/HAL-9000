# ABOUTME: Channel-based conversation tracking system
# ABOUTME: Manages active conversations per channel with timeout and response decisions

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import discord
from pydantic_ai import ModelMessage
from tools import MessageData


@dataclass
class ChannelConversation:
    """State for an active conversation in a channel."""
    channel_id: int
    started_at: datetime
    last_activity: datetime

    # All messages seen during conversation - full channel context for prompt building
    messages: list[MessageData] = field(default_factory=list)

    # Bot's conversation turns only (user question → bot response pairs)
    # Passed to PydanticAI's message_history for conversation continuity
    llm_history: list[ModelMessage] = field(default_factory=list)

    # Users who've participated
    participants: set[int] = field(default_factory=set)

    # When bot last responded (for followup detection)
    last_bot_response: Optional[datetime] = None


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
        initial_messages: list[MessageData]
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

    def record_message(self, channel_id: int, message: MessageData):
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
        Also updates last_bot_response timestamp.
        """
        conv = self._conversations.get(channel_id)
        if conv is None:
            return
        
        conv.llm_history = llm_history
        conv.last_bot_response = datetime.now(timezone.utc)

    def end(self, channel_id: int):
        """End a conversation in a channel."""
        self._conversations.pop(channel_id, None)


class ResponseDecider:
    """Decides when to start conversations and when to respond."""
    
    def __init__(self, followup_window_seconds: int = 60):
        """
        Initialize ResponseDecider.
        
        Args:
            followup_window_seconds: How long after bot speaks to consider followups
        """
        self.followup_window_seconds = followup_window_seconds
    
    def _is_explicit_trigger(
        self,
        message: discord.Message,
        bot_user_id: int
    ) -> bool:
        """Check if message has explicit trigger (@mention or reply to bot)."""
        if bot_user_id in [m.id for m in message.mentions]:
            return True
        
        if message.reference and message.reference.resolved:
            referenced = message.reference.resolved
            if isinstance(referenced, discord.Message) and referenced.author.id == bot_user_id:
                return True
        
        return False
    
    def _seconds_since_bot_spoke(
        self,
        conversation: ChannelConversation
    ) -> Optional[float]:
        """
        Get seconds since bot last spoke, or None if bot hasn't spoken.
        
        Returns:
            Seconds since last bot response, or None if no previous response
        """
        if conversation.last_bot_response is None:
            return None
        
        now = datetime.now(timezone.utc)
        elapsed = (now - conversation.last_bot_response).total_seconds()
        return elapsed
    
    def _looks_like_followup(self, message: discord.Message) -> bool:
        """
        Heuristic: Does this look like a follow-up question?
        
        Checks for:
        - Short messages with question marks
        - Continuation words at start
        """
        content = message.content.lower()
        
        # Short messages with question marks
        if len(content.split()) < 10 and "?" in content:
            return True
        
        # Continuation words
        starters = ["and ", "also ", "what about ", "how about ", "why ", "but "]
        if any(content.startswith(s) for s in starters):
            return True
        
        return False
    
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
        if self._is_explicit_trigger(message, bot_user_id):
            if bot_user_id in [m.id for m in message.mentions]:
                return True, "explicit_mention"
            else:
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
        
        Uses three-tier decision logic:
        - Tier 1: Explicit triggers (always respond)
        - Tier 2: Recent engagement (maybe respond if looks like followup)
        - Tier 3: Don't respond
        
        Returns:
            Tuple of (decision, reason)
        """
        # Tier 1: Explicit triggers (always respond)
        if self._is_explicit_trigger(message, bot_user_id):
            return True, "explicit_trigger"
        
        # Tier 2: Recent engagement (maybe respond)
        seconds_since_bot_spoke = self._seconds_since_bot_spoke(conversation)
        
        if seconds_since_bot_spoke is not None and seconds_since_bot_spoke < self.followup_window_seconds:
            # Bot spoke recently - more likely to respond
            if self._looks_like_followup(message):
                return True, "recent_followup"
        
        # Tier 3: Don't respond
        return False, "no_trigger"
