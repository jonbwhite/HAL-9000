# Discord Productivity Bot

An AI-powered Discord bot that answers questions about channel message history using Claude.

## Features

- **Question Answering**: Ask the bot questions about past discussions in channels
- **Intelligent Tool Use**: Uses pydanticai agents that intelligently fetch relevant message history
- **Natural Interaction**: Simply mention the bot with your question
- **Smart Chunking**: Handles long responses by splitting at natural boundaries
- **Error Handling**: User-friendly error messages with optional debug logging

## Architecture

- **Discord.py**: Discord API integration and event handling
- **PydanticAI**: AI agent framework with tool calling capabilities
- **Anthropic Claude**: LLM for understanding questions and generating responses
- **Pydantic Settings**: Type-safe configuration management

## Setup

### Prerequisites

1. **Discord Bot Token**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to Bot section and create a bot
   - Enable "Message Content Intent" under Privileged Gateway Intents
   - Copy the token

2. **Invite Bot to Server**
   - In Developer Portal, go to OAuth2 > URL Generator
   - Select scopes: `bot`
   - Select permissions: `Read Messages`, `Send Messages`, `Read Message History`
   - Use generated URL to invite bot to your server

3. **Anthropic API Key**
   - Sign up at [Anthropic Console](https://console.anthropic.com/)
   - Generate an API key

### Installation

1. **Clone and enter directory**
   ```bash
   cd discord-bot
   ```

2. **Install Python dependencies**
   ```bash
   poetry install
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your tokens
   ```

   Required variables:
   - `DISCORD_TOKEN`: Your Discord bot token
   - `ANTHROPIC_API_KEY`: Your Anthropic API key

   Optional variables:
   - `DEBUG_CHANNEL_ID`: Discord channel ID for error logging
   - `DEFAULT_MESSAGE_LIMIT`: Max messages to fetch (default: 100)
   - `DEFAULT_TIME_WINDOW_HOURS`: Default hours to look back (default: 24)
   - `MAX_RESPONSE_LENGTH`: Max message length before chunking (default: 2000)

### Running

```bash
poetry run python bot.py
```

## Usage

Mention the bot in any channel with a question:

```
@BotName what did we discuss about the deployment?
@BotName summarize today's conversation
@BotName who mentioned the bug fix?
```

The bot will:
1. Show a typing indicator
2. Use AI to determine what message history to fetch
3. Analyze the messages
4. Respond with an answer

## Development

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=. --cov-report=html

# Run specific test file
poetry run pytest tests/test_agent.py -v
```

### Project Structure

```
discord-bot/
├── bot.py           # Discord client and message handling
├── agent.py         # PydanticAI agent configuration
├── tools.py         # Tool definitions for fetching messages
├── config.py        # Settings with pydantic-settings
├── utils.py         # Helper functions
├── tests/           # Test suite
│   ├── test_bot.py
│   ├── test_agent.py
│   ├── test_tools.py
│   ├── test_config.py
│   └── test_utils.py
└── docs/
    └── plans/       # Implementation plans
```

### Adding New Tools

To add new capabilities:

1. Define tool function in `tools.py`
2. Register tool with agent in `agent.py` using `@productivity_agent.tool`
3. Update system prompt if needed
4. Add tests in `tests/test_tools.py`

Example:

```python
# In tools.py
async def search_messages_tool(query: str, client: discord.Client):
    # Implementation
    pass

# In agent.py (within create_productivity_agent)
@agent.tool
async def search_messages(ctx: AgentContext, deps: AgentDependencies, query: str):
    return await search_messages_tool(query, deps.discord_client)
```

## Troubleshooting

### Bot doesn't respond to mentions

- Verify "Message Content Intent" is enabled in Discord Developer Portal
- Check bot has permissions in the channel
- Verify bot is actually online (check on_ready message in console)

### API errors

- Check API keys are correct in `.env`
- Verify you have API credits (Anthropic)
- Check console for detailed error messages

### Import errors

- Run `poetry install` to ensure all dependencies are installed
- Verify you're using correct Python version (3.13+)

## License

MIT
