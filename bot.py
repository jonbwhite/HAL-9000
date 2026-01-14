# ABOUTME: Discord bot entry point
# ABOUTME: Handles message events and coordinates with AI agent

# Load .env file into environment variables before anything else
from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
from typing import Optional
import discord
from discord import Message
from config import get_settings
from agent import run_agent
from utils import chunk_message
from instrumentation import initialize_instrumentation
from conversation import ConversationManager, ResponseDecider
from tools import MessageData, fetch_messages_tool, FetchMessagesParams
from datetime import datetime, timezone

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)

# Initialize conversation management
settings = get_settings()
conversation_manager = ConversationManager(
    timeout_seconds=settings.conversation_timeout_seconds
)
response_decider = ResponseDecider(
    followup_window_seconds=settings.followup_window_seconds
)


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

    Implements conversation-based message flow:
    1. Filter out bot's own messages
    2. Check for active conversation or should start one
    3. Record message and decide if bot should respond
    """
    # Filter out bot's own messages before any processing
    if message.author == client.user:
        return

    # Verify we're in a text channel
    if not isinstance(message.channel, discord.TextChannel):
        return

    channel_id = message.channel.id
    bot_user_id = client.user.id if client.user else 0

    # Check if there's an active conversation
    conversation = conversation_manager.get(channel_id)
    print(f"Conversation: {conversation}")
    if conversation:
        print(f"Active conversation found in channel: {message.channel.name}")
        # Active conversation exists - record message and check if should respond
        message_data = MessageData(
            author=message.author.display_name,
            author_id=message.author.id,
            content=message.content,
            timestamp=message.created_at,
            is_bot=message.author.bot
        )
        conversation_manager.record_message(channel_id, message_data)

        should_respond, reason = response_decider.should_respond(
            message, conversation, bot_user_id
        )
        print(f"should_respond: {should_respond}, reason: {reason}")

        if should_respond:
            # Extract question (remove bot mention if present)
            question = message.content
            for mention in message.mentions:
                question = question.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
            question = question.strip()

            if not question:
                question = "What is the user asking about based on the recent messages in this channel? Please infer the question from the conversation context."

            # Show typing indicator while processing
            async with message.channel.typing():
                try:
                    # Run the AI agent with conversation context
                    response, new_messages = await run_agent(
                        question=question,
                        channel=message.channel,
                        user=message.author,
                        discord_client=client,
                        conversation=conversation
                    )

                    # Send response (chunked if needed)
                    await send_chunked_response(message.channel, response)

                    # Record bot response in conversation
                    # Append new messages to existing history
                    updated_history = conversation.llm_history + new_messages
                    conversation_manager.record_bot_response(channel_id, updated_history)

                except ValueError as e:
                    await send_error_message(
                        message,
                        error_text=str(e),
                        log_error=f"ValueError: {e}\nQuestion: {question}\nUser: {message.author}"
                    )

                except Exception as e:
                    error_msg = f"I encountered an error processing your question."
                    log_msg = f"Unexpected error:\n{type(e).__name__}: {e}\nQuestion: {question}\nUser: {message.author}"

                    await send_error_message(
                        message,
                        error_text=error_msg,
                        log_error=log_msg
                    )

                    print(f"Error: {e}")
                    import traceback
                    traceback.print_exc()
    else:
        # No active conversation - check if should start one
        should_start, reason = response_decider.should_start_conversation(
            message, bot_user_id
        )
        print(f"should_start_conversation: {should_start}, reason: {reason}")

        if should_start:
            # Load recent messages and start conversation
            # Use fetch_messages_tool with a short time window (1 hour) to get recent context
            try:
                params = FetchMessagesParams(
                    channel_id=channel_id,
                    hours_back=1,  # Last hour for conversation context
                    limit=20  # Reasonable limit for initial context
                )
                recent_messages = await fetch_messages_tool(params, client)
            except Exception:
                # Graceful degradation: start with empty messages
                recent_messages = []

            # Add current message
            message_data = MessageData(
                author=message.author.display_name,
                author_id=message.author.id,
                content=message.content,
                timestamp=message.created_at,
                is_bot=message.author.bot
            )
            recent_messages.append(message_data)

            conversation = conversation_manager.start(channel_id, recent_messages)
            print(f"Conversation started in channel: {message.channel.name}")
            # Extract question (remove bot mention if present)
            question = message.content
            for mention in message.mentions:
                question = question.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
            question = question.strip()

            if not question:
                question = "What is the user asking about based on the recent messages in this channel? Please infer the question from the conversation context."

            # Show typing indicator while processing
            async with message.channel.typing():
                try:
                    # Run the AI agent with conversation context
                    response, new_messages = await run_agent(
                        question=question,
                        channel=message.channel,
                        user=message.author,
                        discord_client=client,
                        conversation=conversation
                    )

                    # Send response (chunked if needed)
                    await send_chunked_response(message.channel, response)

                    # Record bot response in conversation
                    # Append new messages to existing history
                    updated_history = conversation.llm_history + new_messages
                    conversation_manager.record_bot_response(channel_id, updated_history)

                except ValueError as e:
                    await send_error_message(
                        message,
                        error_text=str(e),
                        log_error=f"ValueError: {e}\nQuestion: {question}\nUser: {message.author}"
                    )

                except Exception as e:
                    error_msg = f"I encountered an error processing your question."
                    log_msg = f"Unexpected error:\n{type(e).__name__}: {e}\nQuestion: {question}\nUser: {message.author}"

                    await send_error_message(
                        message,
                        error_text=error_msg,
                        log_error=log_msg
                    )

                    print(f"Error: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            # No trigger to start conversation - just record message if conversation exists
            # (This shouldn't happen since we checked for active conversation above,
            # but keeping for safety)
            pass


def main():
    """Start the Discord bot."""
    settings = get_settings()
    token = settings.discord_token
    if not token:
        raise ValueError('DISCORD_TOKEN not found in environment variables')

    # Initialize OpenTelemetry instrumentation for Langfuse
    initialize_instrumentation(settings)

    print("Starting Discord bot...")
    client.run(token)


if __name__ == '__main__':
    main()
