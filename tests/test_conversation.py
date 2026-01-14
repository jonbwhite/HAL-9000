# ABOUTME: Tests for conversation management system
# ABOUTME: Validates ConversationManager, ResponseDecider, and conversation lifecycle

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
import discord
from conversation import (
    ConversationManager,
    ResponseDecider,
    ChannelConversation,
    MessageRecord
)


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

    message = MessageRecord(
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
        MessageRecord(
            author="User1",
            author_id=111,
            content="Message 1",
            timestamp=datetime.now(timezone.utc),
            is_bot=False
        ),
        MessageRecord(
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

    message = MessageRecord(
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

    message1 = MessageRecord(
        author="User1",
        author_id=111,
        content="First",
        timestamp=datetime.now(timezone.utc),
        is_bot=False
    )
    message2 = MessageRecord(
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
    
    message = MessageRecord(
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


def test_should_respond_same_as_should_start():
    """For Phase 1, should_respond uses same logic as should_start_conversation."""
    decider = ResponseDecider()
    
    message = Mock(spec=discord.Message)
    message.mentions = [Mock(id=999)]
    message.reference = None
    
    conversation = Mock(spec=ChannelConversation)
    
    should_respond, reason = decider.should_respond(message, conversation, bot_user_id=999)
    
    assert should_respond is True
    assert reason == "explicit_mention"


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
        MessageRecord(
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
