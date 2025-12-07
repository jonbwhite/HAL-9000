# ABOUTME: Discord bot entry point
# ABOUTME: Handles message events and coordinates with AI agent

import os
import asyncio
from typing import Optional
import discord
from discord import Message
from config import get_settings
from agent import run_agent
from utils import chunk_message

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    """Called when bot successfully connects to Discord."""
    print(f'{client.user} has connected to Discord!')
    print(f'Bot is in {len(client.guilds)} guilds')


async def send_error_message(
    message: Message,
    error_text: str,
    log_error: Optional[str] = None
):
    """
    Send user-friendly error message and optionally log to debug channel.

    Args:
        message: Original Discord message
        error_text: User-friendly error message
        log_error: Detailed error for debug channel
    """
    await message.channel.send(f"Sorry, {error_text}")

    settings = get_settings()
    if log_error and settings.debug_channel_name:
        if isinstance(message.channel, discord.TextChannel) and message.channel.guild:
            debug_channel = discord.utils.get(
                message.channel.guild.text_channels,
                name=settings.debug_channel_name
            )
            if debug_channel:
                await debug_channel.send(f"Error in {message.channel.mention}:\n```\n{log_error}\n```")


async def send_chunked_response(channel: discord.TextChannel, response: str):
    """
    Send response to Discord, chunking if necessary.

    Args:
        channel: Channel to send to
        response: Response text to send
    """
    settings = get_settings()
    chunks = chunk_message(response, max_length=settings.max_response_length)

    for chunk in chunks:
        await channel.send(chunk)


@client.event
async def on_message(message: Message):
    """
    Handle incoming Discord messages.

    Responds when bot is mentioned with a question. If mentioned without
    an explicit question, infers the question from recent channel messages.
    """
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Check if bot is mentioned
    if client.user not in message.mentions:
        return

    # Extract question (remove bot mention)
    question = message.content
    for mention in message.mentions:
        question = question.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
    question = question.strip()

    # If no explicit question, try to infer from recent messages
    if not question:
        question = "What is the user asking about based on the recent messages in this channel? Please infer the question from the conversation context."

    # Verify we're in a text channel
    if not isinstance(message.channel, discord.TextChannel):
        await message.channel.send("I can only answer questions in text channels.")
        return

    # Show typing indicator while processing
    async with message.channel.typing():
        try:
            # Run the AI agent
            response = await run_agent(
                question=question,
                channel=message.channel,
                user=message.author,
                discord_client=client
            )

            # Send response (chunked if needed)
            await send_chunked_response(message.channel, response)

        except ValueError as e:
            # User-facing errors (channel not found, etc.)
            await send_error_message(
                message,
                error_text=str(e),
                log_error=f"ValueError: {e}\nQuestion: {question}\nUser: {message.author}"
            )

        except Exception as e:
            # Unexpected errors
            error_msg = f"I encountered an error processing your question."
            log_msg = f"Unexpected error:\n{type(e).__name__}: {e}\nQuestion: {question}\nUser: {message.author}"

            await send_error_message(
                message,
                error_text=error_msg,
                log_error=log_msg
            )

            # Also print to console for local debugging
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Start the Discord bot."""
    settings = get_settings()
    token = settings.discord_token
    if not token:
        raise ValueError('DISCORD_TOKEN not found in environment variables')

    print("Starting Discord bot...")
    client.run(token)


if __name__ == '__main__':
    main()
