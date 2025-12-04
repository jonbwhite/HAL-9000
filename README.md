# Discord Bot

A Discord bot built with discord.py and pydanticai.

## Setup

1. Copy `.env.example` to `.env` and add your Discord bot token:
   ```bash
   cp .env.example .env
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

3. Run the bot:
   ```bash
   poetry run python bot.py
   ```

## Development

This project uses:
- [asdf](https://asdf-vm.com/) for Python version management
- [Poetry](https://python-poetry.org/) for dependency management
- [discord.py](https://discordpy.readthedocs.io/) for Discord API integration
- [pydanticai](https://ai.pydantic.dev/) for AI capabilities
