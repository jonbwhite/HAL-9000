# Conversation Management Plan

This document outlines the design for channel-based conversation tracking, allowing the bot to participate naturally in ongoing discussions.

## Goals

1. Bot participates in conversations like a person - attentive after being engaged
2. Multiple users can participate in a single conversation with the bot
3. Context accumulates naturally throughout a conversation
4. Clean abstractions for future enhancement (smarter response decisions, LLM-as-judge)

## Scope

Guild text channels only. DMs and threads are out of scope for this implementation.

## Core Concepts

### Conversation Per Channel

Instead of tracking "user X is talking to bot", we track "there's a conversation in channel Y that the bot is part of."

- One active conversation per channel at a time
- Any user can participate in the conversation
- Bot sees all messages while conversation is active (even ones it doesn't respond to)
- Conversation ends after inactivity timeout

### Activity-Based Timeout

- Timeout resets on **any** message in the channel, not just ones the bot responds to
- This models how humans stay attentive to an active discussion
- Default: 120 seconds of inactivity ends the conversation

### Two Decision Points

1. **Should we start a conversation?** - Currently: explicit triggers only
2. **Should we respond to this message?** - Currently: explicit triggers, future: heuristics/LLM

---

## Data Structures

### MessageRecord

Lightweight representation of a Discord message:

```python
@dataclass
class MessageRecord:
    author: str
    author_id: int
    content: str
    timestamp: datetime
    is_bot: bool
```

### ChannelConversation

State for an active conversation:

```python
@dataclass
class ChannelConversation:
    channel_id: int
    started_at: datetime
    last_activity: datetime

    # All messages seen during conversation - full channel context for prompt building
    messages: list[MessageRecord]

    # Bot's conversation turns only (user question → bot response pairs)
    # Passed to PydanticAI's message_history for conversation continuity
    llm_history: list[ModelMessage]

    # Users who've participated
    participants: set[int]
```

---

## Components

### ConversationManager

Manages active conversations per channel:

```python
class ConversationManager:
    def __init__(self, timeout_seconds: int = 120):
        self.timeout = timeout_seconds
        self._conversations: dict[int, ChannelConversation] = {}

    def get(self, channel_id: int) -> Optional[ChannelConversation]
    def start(self, channel_id: int, initial_messages: list[MessageRecord]) -> ChannelConversation
    def record_message(self, channel_id: int, message: MessageRecord)
    def record_bot_response(self, channel_id: int, llm_history: list[ModelMessage])
    def end(self, channel_id: int)
```

**Behavior:**
- `get()` returns None if conversation expired (checks timeout)
- `record_message()` appends message AND bumps `last_activity`
- No message cap in storage; timeout naturally bounds conversation length
- Prompt construction may truncate for LLM context limits (separate concern)

### ResponseDecider

Abstracts the decision logic for when to engage:

```python
class ResponseDecider:
    def should_start_conversation(
        self,
        message: Message,
        bot_user_id: int
    ) -> tuple[bool, str]:
        """Should this message start a new conversation? Returns (decision, reason)."""

    def should_respond(
        self,
        message: Message,
        conversation: ChannelConversation,
        bot_user_id: int
    ) -> tuple[bool, str]:
        """Should bot respond to this message? Returns (decision, reason)."""
```

---

## Message Flow

```
Message arrives
      │
      ▼
┌───────────────────────────────┐
│ Is message from self? → STOP  │
└───────────────────────────────┘
      │ NO
      ▼
┌─────────────────────────────────────────────────────┐
│ Is there an active conversation in this channel?    │
└─────────────────────────────────────────────────────┘
      │                              │
      │ YES                          │ NO
      ▼                              ▼
┌─────────────────┐    ┌──────────────────────────────┐
│ Record message  │    │ should_start_conversation()? │
│ (bumps timeout) │    └──────────────────────────────┘
└─────────────────┘           │              │
      │                       │ YES          │ NO
      ▼                       ▼              ▼
┌─────────────────┐    ┌─────────────┐    (ignore)
│ should_respond? │    │ Load recent │
└─────────────────┘    │ messages,   │
      │                │ start conv  │
      │                └─────────────┘
      ▼                       │
  YES / NO                    ▼
      │              ┌─────────────────┐
      │              │ should_respond? │
      ▼              └─────────────────┘
┌─────────────┐              │
│ If YES:     │              ▼
│ - Run agent │         (always YES
│ - Send resp │          for trigger)
│ - Record    │
└─────────────┘
```

---

## Implementation Phases

### Phase 1: Basic Structure

**Files:**
- `conversation.py` - ChannelConversation, ConversationManager, ResponseDecider

**Behavior:**
- Filter out bot's own messages before any processing
- `should_start_conversation`: True if @mentioned or reply to bot
- `should_respond`: True if @mentioned or reply to bot (same as start, for now)
- Timeout: 120 seconds, bumped on any message

**Integration:**
- Update `bot.py` to use ConversationManager
- Pass conversation context to agent instead of fetching fresh each time

### Phase 2: Context in Agent

**Changes:**
- Update `run_agent()` to accept conversation's accumulated messages
- Use `conversation.llm_history` for PydanticAI's `message_history` parameter
- Bot responses maintain continuity across multiple exchanges

**Result:**
- User asks question → Bot responds
- User follows up → Bot remembers what it said
- Different user asks related question → Bot has full context

### Phase 3: Smarter Response Decisions

**Add heuristics to `should_respond`:**

```python
def should_respond(self, message, conversation, bot_user_id) -> tuple[bool, str]:
    # Tier 1: Explicit triggers (always respond)
    if self._is_explicit_trigger(message, bot_user_id):
        return True, "explicit_trigger"

    # Tier 2: Recent engagement (maybe respond)
    seconds_since_bot_spoke = self._seconds_since_bot_spoke(conversation)

    if seconds_since_bot_spoke and seconds_since_bot_spoke < 60:
        # Bot spoke recently - more likely to respond
        if self._looks_like_followup(message):
            return True, "recent_followup"

    # Tier 3: Don't respond
    return False, "no_trigger"

def _looks_like_followup(self, message) -> bool:
    """Heuristic: Does this look like a follow-up question?"""
    content = message.content.lower()

    # Short messages with question marks
    if len(content.split()) < 10 and "?" in content:
        return True

    # Continuation words
    starters = ["and ", "also ", "what about ", "how about ", "why ", "but "]
    if any(content.startswith(s) for s in starters):
        return True

    return False
```

**Logging:** Log all `should_respond` and `should_start_conversation` decisions with their reason strings. This enables auditing and tuning heuristics based on real usage.

### Phase 4: LLM-as-Judge for Response Decision

**For ambiguous cases, ask a fast model:**

```python
async def should_respond(self, message, conversation, bot_user_id) -> tuple[bool, str]:
    # Tier 1 & 2: Same as Phase 3
    # ...

    # Tier 3: LLM decides for ambiguous cases
    if self._is_ambiguous(message, conversation):
        should = await self._ask_llm_judge(message, conversation)
        return should, "llm_judge"

    return False, "no_trigger"

async def _ask_llm_judge(self, message, conversation) -> bool:
    prompt = f"""You're a Discord bot in an active conversation.

Recent messages:
{self._format_recent(conversation)}

New message from {message.author.display_name}: "{message.content}"

Should you respond to this message?
- YES if it's directed at you or continues the discussion you're part of
- NO if it's a side conversation or not meant for you

Answer only YES or NO."""

    result = await self.judge_agent.run(prompt)
    return result.output.strip().upper() == "YES"
```

---

## Configuration

```python
# config.py additions

class Settings(BaseSettings):
    # Conversation settings
    conversation_timeout_seconds: int = 120

    # Response decision settings
    followup_window_seconds: int = 60  # How long after bot speaks to consider followups
    use_llm_judge: bool = False  # Enable LLM-as-judge for ambiguous cases
```

---

## Testing Strategy

### Unit Tests

```python
# test_conversation.py

def test_conversation_expires_after_timeout():
    manager = ConversationManager(timeout_seconds=60)
    conv = manager.start(channel_id=123, initial_messages=[])

    # Simulate time passing
    conv.last_activity = datetime.now(timezone.utc) - timedelta(seconds=61)

    assert manager.get(123) is None

def test_message_bumps_timeout():
    manager = ConversationManager(timeout_seconds=60)
    conv = manager.start(channel_id=123, initial_messages=[])

    original_activity = conv.last_activity

    manager.record_message(123, MessageRecord(...))

    assert conv.last_activity > original_activity

def test_bot_messages_filtered():
    """Bot's own messages don't trigger conversation logic."""
    # Verify on_message early-returns for bot's own messages
```

### Integration Tests

```python
# test_conversation_integration.py

async def test_followup_uses_llm_history():
    """Bot remembers what it said when user follows up."""
    # 1. Trigger conversation with @mention
    # 2. Bot responds
    # 3. Same user sends follow-up (no @mention)
    # 4. Verify bot response references previous exchange

async def test_other_user_joins_conversation():
    """Different user can participate in active conversation."""
    # 1. User A triggers conversation
    # 2. Bot responds
    # 3. User B asks follow-up question
    # 4. Verify bot responds with full context
```

---

## Deployment Notes

**State Management:**
- In-memory storage (dict of channel_id → ChannelConversation)
- State lost on restart - acceptable with short timeout
- No Redis/database needed for single instance

**Memory Bounds:**
- Conversations expire after timeout (120s default)
- With short timeout, message count naturally bounded
- Memory usage minimal for single instance

**Railway Specifics:**
- Single instance = no distributed state concerns
- Occasional deploys lose active conversations (low impact)
- No additional infrastructure needed

---

## Future Considerations

### Thread Support
- Option to create Discord thread for conversation
- All messages in thread are part of conversation
- Cleaner separation, no timeout needed

### Topic Tracking
- Summarize what conversation is "about"
- Detect topic changes (new conversation?)
- Better context for LLM responses

### Conversation Metrics
- Track conversation length, participant count
- Feed into eval system
- Identify patterns in successful vs. failed conversations

### Proactive Participation
- Bot notices confusion and offers help
- Bot adds relevant information unprompted
- Requires careful tuning to avoid being annoying
