# ABOUTME: Tests for conversation management system
# ABOUTME: Validates ConversationManager, ResponseDecider, and conversation lifecycle

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
import discord
from conversation import (
    ConversationManager,
    ResponseDecider,
    ChannelConversation
)
from tools import MessageData


def test_conversation_expires_after_timeout():
    """Conversation should expire after timeout period."""
    manager = ConversationManager(timeout_seconds=60)
    conv = manager.start(channel_id=123, initial_messages=[])

    # Simulate time passing beyond timeout
    conv.last_activity = datetime.now(timezone.utc) - timedelta(seconds=61)

    assert manager.get(123) is None


def test_conversation_active_within_timeout():
    """Conversation should remain active within timeout period."""
    manager = ConversationManager(timeout_seconds=60)
    conv = manager.start(channel_id=123, initial_messages=[])

    # Simulate time passing but within timeout
    conv.last_activity = datetime.now(timezone.utc) - timedelta(seconds=30)

    result = manager.get(123)
    assert result is not None
    assert result.channel_id == 123


def test_message_bumps_timeout():
    """Recording a message should update last_activity timestamp."""
    manager = ConversationManager(timeout_seconds=60)
    conv = manager.start(channel_id=123, initial_messages=[])

    original_activity = conv.last_activity

    # Wait a moment to ensure timestamp difference
    import time
    time.sleep(0.1)

    message = MessageData(
        author="TestUser",
        author_id=456,
        content="Test message",
        timestamp=datetime.now(timezone.utc),
        is_bot=False
    )
    manager.record_message(123, message)

    # Get conversation again to check updated activity
    updated_conv = manager.get(123)
    assert updated_conv is not None
    assert updated_conv.last_activity > original_activity


def test_start_conversation_adds_participants():
    """Starting conversation should add participants from initial messages."""
    manager = ConversationManager()
    
    initial_messages = [
        MessageData(
            author="User1",
            author_id=111,
            content="Message 1",
            timestamp=datetime.now(timezone.utc),
            is_bot=False
        ),
        MessageData(
            author="User2",
            author_id=222,
            content="Message 2",
            timestamp=datetime.now(timezone.utc),
            is_bot=False
        )
    ]
    
    conv = manager.start(channel_id=123, initial_messages=initial_messages)
    
    assert 111 in conv.participants
    assert 222 in conv.participants
    assert len(conv.participants) == 2


def test_record_message_adds_participant():
    """Recording a message should add author to participants."""
    manager = ConversationManager()
    conv = manager.start(channel_id=123, initial_messages=[])

    message = MessageData(
        author="NewUser",
        author_id=999,
        content="New message",
        timestamp=datetime.now(timezone.utc),
        is_bot=False
    )
    manager.record_message(123, message)

    updated_conv = manager.get(123)
    assert 999 in updated_conv.participants


def test_record_message_appends_to_messages():
    """Recording a message should append to messages list."""
    manager = ConversationManager()
    conv = manager.start(channel_id=123, initial_messages=[])

    message1 = MessageData(
        author="User1",
        author_id=111,
        content="First",
        timestamp=datetime.now(timezone.utc),
        is_bot=False
    )
    message2 = MessageData(
        author="User2",
        author_id=222,
        content="Second",
        timestamp=datetime.now(timezone.utc),
        is_bot=False
    )

    manager.record_message(123, message1)
    manager.record_message(123, message2)

    updated_conv = manager.get(123)
    assert len(updated_conv.messages) == 2
    assert updated_conv.messages[0].content == "First"
    assert updated_conv.messages[1].content == "Second"


def test_record_message_no_conversation():
    """Recording message when no conversation exists should do nothing."""
    manager = ConversationManager()
    
    message = MessageData(
        author="User",
        author_id=111,
        content="Test",
        timestamp=datetime.now(timezone.utc),
        is_bot=False
    )
    
    # Should not raise error
    manager.record_message(999, message)
    
    assert manager.get(999) is None


def test_end_conversation():
    """Ending a conversation should remove it."""
    manager = ConversationManager()
    manager.start(channel_id=123, initial_messages=[])
    
    assert manager.get(123) is not None
    
    manager.end(123)
    
    assert manager.get(123) is None


def test_response_decider_explicit_mention():
    """ResponseDecider should return True for explicit @mention."""
    decider = ResponseDecider()
    
    message = Mock(spec=discord.Message)
    message.mentions = [Mock(id=999)]
    message.reference = None
    
    should_start, reason = decider.should_start_conversation(message, bot_user_id=999)
    
    assert should_start is True
    assert reason == "explicit_mention"


def test_response_decider_reply_to_bot():
    """ResponseDecider should return True for reply to bot message."""
    decider = ResponseDecider()
    
    bot_message = Mock(spec=discord.Message)
    bot_message.author.id = 999
    
    message = Mock(spec=discord.Message)
    message.mentions = []
    message.reference = Mock()
    message.reference.resolved = bot_message
    
    should_start, reason = decider.should_start_conversation(message, bot_user_id=999)
    
    assert should_start is True
    assert reason == "reply_to_bot"


def test_response_decider_no_trigger():
    """ResponseDecider should return False when no trigger present."""
    decider = ResponseDecider()
    
    message = Mock(spec=discord.Message)
    message.mentions = []
    message.reference = None
    
    should_start, reason = decider.should_start_conversation(message, bot_user_id=999)
    
    assert should_start is False
    assert reason == "no_trigger"


def test_response_decider_reply_to_other_user():
    """ResponseDecider should return False for reply to non-bot message."""
    decider = ResponseDecider()
    
    other_message = Mock(spec=discord.Message)
    other_message.author.id = 888
    
    message = Mock(spec=discord.Message)
    message.mentions = []
    message.reference = Mock()
    message.reference.resolved = other_message
    
    should_start, reason = decider.should_start_conversation(message, bot_user_id=999)
    
    assert should_start is False
    assert reason == "no_trigger"


def test_should_respond_explicit_trigger_mention():
    """Phase 3: should_respond returns True for explicit @mention."""
    decider = ResponseDecider()
    
    message = Mock(spec=discord.Message)
    message.mentions = [Mock(id=999)]
    message.reference = None
    
    conversation = Mock(spec=ChannelConversation)
    
    should_respond, reason = decider.should_respond(message, conversation, bot_user_id=999)
    
    assert should_respond is True
    assert reason == "explicit_trigger"


def test_should_respond_explicit_trigger_reply():
    """Phase 3: should_respond returns True for reply to bot."""
    decider = ResponseDecider()
    
    bot_message = Mock(spec=discord.Message)
    bot_message.author.id = 999
    
    message = Mock(spec=discord.Message)
    message.mentions = []
    message.reference = Mock()
    message.reference.resolved = bot_message
    
    conversation = Mock(spec=ChannelConversation)
    
    should_respond, reason = decider.should_respond(message, conversation, bot_user_id=999)
    
    assert should_respond is True
    assert reason == "explicit_trigger"


def test_should_respond_recent_followup():
    """Phase 3: should_respond returns True for followup question after recent bot response."""
    decider = ResponseDecider(followup_window_seconds=60)
    
    message = Mock(spec=discord.Message)
    message.mentions = []
    message.reference = None
    message.content = "Why is that?"
    
    conversation = ChannelConversation(
        channel_id=123,
        started_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        last_bot_response=datetime.now(timezone.utc) - timedelta(seconds=30)  # 30 seconds ago
    )
    
    should_respond, reason = decider.should_respond(message, conversation, bot_user_id=999)
    
    assert should_respond is True
    assert reason == "recent_followup"


def test_should_respond_no_response_old_bot_message():
    """Phase 3: should_respond returns False when bot spoke too long ago."""
    decider = ResponseDecider(followup_window_seconds=60)
    
    message = Mock(spec=discord.Message)
    message.mentions = []
    message.reference = None
    message.content = "Why is that?"
    
    conversation = ChannelConversation(
        channel_id=123,
        started_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        last_bot_response=datetime.now(timezone.utc) - timedelta(seconds=90)  # 90 seconds ago (beyond window)
    )
    
    should_respond, reason = decider.should_respond(message, conversation, bot_user_id=999)
    
    assert should_respond is False
    assert reason == "no_trigger"


def test_should_respond_no_response_not_followup():
    """Phase 3: should_respond returns False when message doesn't look like followup."""
    decider = ResponseDecider(followup_window_seconds=60)
    
    message = Mock(spec=discord.Message)
    message.mentions = []
    message.reference = None
    message.content = "This is a long message that doesn't look like a followup question at all"
    
    conversation = ChannelConversation(
        channel_id=123,
        started_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        last_bot_response=datetime.now(timezone.utc) - timedelta(seconds=30)  # 30 seconds ago
    )
    
    should_respond, reason = decider.should_respond(message, conversation, bot_user_id=999)
    
    assert should_respond is False
    assert reason == "no_trigger"


def test_should_respond_no_response_no_bot_history():
    """Phase 3: should_respond returns False when bot hasn't spoken yet."""
    decider = ResponseDecider(followup_window_seconds=60)
    
    message = Mock(spec=discord.Message)
    message.mentions = []
    message.reference = None
    message.content = "Why is that?"
    
    conversation = ChannelConversation(
        channel_id=123,
        started_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        last_bot_response=None  # Bot hasn't spoken
    )
    
    should_respond, reason = decider.should_respond(message, conversation, bot_user_id=999)
    
    assert should_respond is False
    assert reason == "no_trigger"


def test_looks_like_followup_short_question():
    """_looks_like_followup returns True for short messages with question marks."""
    decider = ResponseDecider()
    
    message = Mock(spec=discord.Message)
    message.content = "Why?"
    
    assert decider._looks_like_followup(message) is True


def test_looks_like_followup_continuation_word():
    """_looks_like_followup returns True for messages starting with continuation words."""
    decider = ResponseDecider()
    
    test_cases = [
        "and what about that?",
        "also how does it work?",
        "what about the other one?",
        "how about this?",
        "why is that?",
        "but what if?"
    ]
    
    for content in test_cases:
        message = Mock(spec=discord.Message)
        message.content = content
        assert decider._looks_like_followup(message) is True, f"Failed for: {content}"


def test_looks_like_followup_not_followup():
    """_looks_like_followup returns False for messages that don't look like followups."""
    decider = ResponseDecider()
    
    test_cases = [
        "This is a long message that doesn't look like a followup",
        "Just a regular statement",
        "No question mark here"
    ]
    
    for content in test_cases:
        message = Mock(spec=discord.Message)
        message.content = content
        assert decider._looks_like_followup(message) is False, f"Failed for: {content}"


def test_seconds_since_bot_spoke():
    """_seconds_since_bot_spoke returns correct elapsed time."""
    decider = ResponseDecider()
    
    now = datetime.now(timezone.utc)
    conversation = ChannelConversation(
        channel_id=123,
        started_at=now,
        last_activity=now,
        last_bot_response=now - timedelta(seconds=45)
    )
    
    elapsed = decider._seconds_since_bot_spoke(conversation)
    
    assert elapsed is not None
    assert 44.9 < elapsed < 45.1  # Allow small timing variance


def test_seconds_since_bot_spoke_none():
    """_seconds_since_bot_spoke returns None when bot hasn't spoken."""
    decider = ResponseDecider()
    
    conversation = ChannelConversation(
        channel_id=123,
        started_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        last_bot_response=None
    )
    
    elapsed = decider._seconds_since_bot_spoke(conversation)
    
    assert elapsed is None


def test_record_bot_response_updates_timestamp():
    """Recording bot response should update last_bot_response timestamp."""
    manager = ConversationManager()
    conv = manager.start(channel_id=123, initial_messages=[])
    
    assert conv.last_bot_response is None
    
    # Use empty list for llm_history (ModelMessage is a union type, can't instantiate directly)
    llm_history = []
    
    manager.record_bot_response(123, llm_history)
    
    updated_conv = manager.get(123)
    assert updated_conv is not None
    assert updated_conv.last_bot_response is not None
    assert updated_conv.llm_history == llm_history


def test_multiple_conversations_different_channels():
    """Manager should handle multiple conversations in different channels."""
    manager = ConversationManager()
    
    conv1 = manager.start(channel_id=111, initial_messages=[])
    conv2 = manager.start(channel_id=222, initial_messages=[])
    
    assert manager.get(111) is not None
    assert manager.get(222) is not None
    assert manager.get(111) != manager.get(222)


def test_conversation_stores_initial_messages():
    """Starting conversation should store initial messages."""
    manager = ConversationManager()
    
    initial = [
        MessageData(
            author="User",
            author_id=111,
            content="Initial message",
            timestamp=datetime.now(timezone.utc),
            is_bot=False
        )
    ]
    
    conv = manager.start(channel_id=123, initial_messages=initial)
    
    assert len(conv.messages) == 1
    assert conv.messages[0].content == "Initial message"
