# shadowsprite/utils/error_handler.py

import logging, sys, traceback
from discord import Embed
from discord.abc import Messageable
from shadowsprite.config import DISCORD_LOG_CHANNEL_ID
from telegram import Update
from telegram.ext import ContextTypes

# --- Logger setup: send error logs to stderr for systemd to capture ---
logger = logging.getLogger("shadowsprite")
logger.setLevel(logging.ERROR)
if not logger.handlers:
    sh = logging.StreamHandler(sys.stderr)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    sh.setFormatter(fmt)
    logger.addHandler(sh)

def chunked_traceback(tb: str, max_size: int):
    for i in range(0, len(tb), max_size):
        yield tb[i:i + max_size]

async def report_discord_error(bot_client, interaction, command_name, error):
    """
    Log error to file and send embed to the configured Discord log channel.
    """
    tb = traceback.format_exc()
    # 1) Log to disk
    logger.error(f"Error in {command_name} by {interaction.user}:\n{tb}")
    # 2) Notify in Discord channel
    channel = bot_client.get_channel(DISCORD_LOG_CHANNEL_ID)
    if channel:
        embed = Embed(
            title=f"Error in {command_name}",
            description=(
                f"**User:** {interaction.user.mention}\n"
                f"**Guild:** {interaction.guild_id}\n"
                f"**Error:** `{error}`"
            ),
            color=0xE74C3C
        )
        trace_field = tb if len(tb) < 1024 else tb[-1024:]
        embed.add_field(name="Traceback", value=f"```py\n{trace_field}\n```", inline=False)
        await channel.send(embed=embed)


async def report_telegram_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    Log Telegram errors to file and relay them into the Discord log channel.
    Splits the traceback into 1024-char fenced chunks so Discord will accept it.
    """
    # 1) Extract the exception and full traceback
    error = context.error
    if error is not None:
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    else:
        tb = "No traceback available"

    # 2) Log locally
    logger.error("🚨 Telegram handler error:\n%s\n%s", error, tb)

    # 3) Get the Discord channel
    try:
        channel_id = int(DISCORD_LOG_CHANNEL_ID)
    except Exception:
        logger.exception("Invalid DISCORD_LOG_CHANNEL_ID %r", DISCORD_LOG_CHANNEL_ID)
        return

    from shadowsprite.platforms.discord_bot import bot as discord_bot
    channel = discord_bot.get_channel(channel_id)
    if channel is None:
        logger.warning("Discord log channel %d not found", channel_id)
        return
    if not isinstance(channel, Messageable):
        logger.warning(
            "Discord log channel %r is not messageable (type=%s)",
            channel, type(channel).__name__
        )
        return

    # 4) Build the base embed
    if isinstance(update, Update):
        user = update.effective_user.id if update.effective_user else "unknown"
        chat = update.effective_chat.id if update.effective_chat else "unknown"
    else:
        user = "unknown"
        chat = "unknown"

    embed = Embed(
        title="Error in Telegram handler",
        description=(
            f"**User:** {user}\n"
            f"**Chat:** {chat}\n"
            f"**Error:** `{error}`"
        ),
        color=0xE74C3C
    )

    # 5) Split the traceback into chunks that fit within Discord's 1024-char limit
    FENCE_PREFIX = "```py\n"
    FENCE_SUFFIX = "\n```"
    MAX_FIELD_LEN = 1024

    # calculate how many characters of the raw traceback per chunk
    max_tb_chunk = MAX_FIELD_LEN - (len(FENCE_PREFIX) + len(FENCE_SUFFIX))

    # iterate over the traceback in slices
    for idx in range(0, len(tb), max_tb_chunk):
        chunk = tb[idx : idx + max_tb_chunk]
        field_name = "Traceback" if idx == 0 else f"Traceback (cont. {idx // max_tb_chunk})"
        embed.add_field(
            name=field_name,
            value=f"{FENCE_PREFIX}{chunk}{FENCE_SUFFIX}",
            inline=False
        )

    # 6) Send the embed via the bot's loop
    try:
        discord_bot.loop.create_task(channel.send(embed=embed))
        logger.info("Scheduled Telegram error report to Discord channel %d", channel_id)
    except Exception:
        logger.exception("Failed to schedule error-report task on Discord loop")