"""
platforms/discord_bot.py

Discord adapter for the ShadowDaemon bot.
Handles incoming Discord updates and commands, delegates to core logic, and formats responses. 
Includes handlers for:
  - on_ready:
  - on_guild_join:
  - help_command: responding to /help
  - roll: processing /r dice rolls
  - roll_alias:
  - ed:
  - start:
"""

import discord
from discord.ext import commands
from discord import app_commands, Member, Object
from shadowsprite.config import (
    DISCORD_TOKEN,
    ALLOWED_EDITIONS,
    RAW_ALLOWED,
    BOT_USAGE_PROMPT,
    HELP_TEXT,
    DISCORD_TEST_GUILD_ID,
)
from shadowsprite.core.db_crud import (
    get_edition,
    get_chat_edition,
    set_edition
)
from shadowsprite.core.dice_roller import parse_roll_args, get_roll_results
from shadowsprite.platforms.bot_helper import format_for_discord
from shadowsprite.utils.error_handler import report_discord_error

# --- Configure intents (no message content needed for slash commands) ---
intents = discord.Intents.default()
intents.guilds = True

class ShadowSprite(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=[], help_command=None, intents=intents)

    async def setup_hook(self):
        # Sync test Guild 
        #guild = discord.Object(id=int(DISCORD_TEST_GUILD_ID))
        #self.tree.clear_commands(guild=guild)
        #await self.tree.sync(guild=guild)

        # Sync globally
        await self.tree.sync()


bot = ShadowSprite()

@bot.event
async def on_ready():
    print(f"Discord bot ready as {bot.user}")

@bot.event
async def on_guild_join(guild: discord.Guild):
    # Greet when added to a new guild and initialize edition
    edition = get_chat_edition(guild.id)
    channel = guild.system_channel or next(
        (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
        None
    )
    if channel:
        await channel.send(
            f"Hello! I’ve initialized this server’s edition to **{edition}**."
            f"\nUse `/ed <edition>` to change it."
        )


# ---------------- Slash Commands ----------------

@bot.tree.command(name="help", description="Show help information for ShadowDaemon")
async def help_command(interaction: discord.Interaction):
    await interaction.response.send_message(HELP_TEXT, ephemeral=True)


async def do_roll(
    interaction: discord.Interaction,
    expression: str
):
    try:
        user_id = interaction.user.id
        if interaction.guild_id:
            chat_id, chat_type = interaction.guild_id, "group"
        else:
            chat_id, chat_type = interaction.user.id, "private"

        edition = get_edition(user_id, chat_id, chat_type)
        try:
            parts = expression.split()
            dice, edge, limit, threshold, comment = parse_roll_args(parts, edition)
        except ValueError:
            return await interaction.response.send_message(BOT_USAGE_PROMPT, ephemeral=True)

        result = get_roll_results(dice, edge, limit, threshold, edition)
        output = format_for_discord(result, edition, edge, comment)
        await interaction.response.send_message(output)
    except ValueError:
        # bad usage
        await interaction.response.send_message(BOT_USAGE_PROMPT, ephemeral=True)
    except Exception as e:
        # central error reporting
        await report_discord_error(bot, interaction, "/r", e)
        # generic user message
        await interaction.response.send_message(
            "⚠️ Something went wrong, the Maker has been notified.",
            ephemeral=True
        )


@bot.tree.command(name="r", description="Roll Shadowrun dice")
@app_commands.describe(expression="Dice expression and options, e.g. '10 5 Comment'")
async def roll(interaction: discord.Interaction, expression: str):
    await do_roll(interaction, expression)


@bot.tree.command(name="roll", description="Roll Shadowrun dice (alias for /r)")
@app_commands.describe(expression="Dice expression and options, e.g. '10 5 Comment'")
async def roll_alias(interaction: discord.Interaction, expression: str):
    await do_roll(interaction, expression)


@bot.tree.command(name="ed", description="Set or view Shadowrun edition for this context")
@app_commands.describe(edition="New edition (e.g., SR5)")
async def ed(
    interaction: discord.Interaction,
    edition: str = ""
):
    if not edition:
        return await interaction.response.send_message(
            f"Usage: `/ed <edition>`\nAllowed: {ALLOWED_EDITIONS}",
            ephemeral=True
        )

    inp = edition.upper()
    if inp not in RAW_ALLOWED:
        return await interaction.response.send_message(
            f"Invalid edition. Choose from: {ALLOWED_EDITIONS}",
            ephemeral=True
        )
    edition_name = inp if inp.startswith("SR") else f"SR{inp}"

    if interaction.guild_id and isinstance(interaction.user, Member):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Only server admins can change the edition here.",
                ephemeral=True
            )
        chat_id, chat_type = interaction.guild_id, "group"
    else:
        chat_id, chat_type = interaction.user.id, "private"

    set_edition(
        user_id=interaction.user.id,
        chat_id=chat_id,
        chat_type=chat_type,
        edition=edition_name
    )
    await interaction.response.send_message(f"✅ Edition set to **{edition_name}**.")


@bot.tree.command(name="start", description="Initialize your personal settings")
async def start(
    interaction: discord.Interaction
):
    if interaction.guild_id:
        return await interaction.response.send_message(
            "Use me in DMs to initialize your settings with `/start`.",
            ephemeral=True
        )
    user_id = interaction.user.id
    chat_id, chat_type = interaction.user.id, "private"
    edition = get_edition(user_id, chat_id, chat_type)
    await interaction.response.send_message(
        f"Welcome! Your settings are initialized to **{edition}** edition."
        "\nUse `/ed <edition>` to change.",
        ephemeral=True
    )


# -------------- Entry Point --------------

def main():
    if not DISCORD_TOKEN:
        raise ValueError("Missing DISCORD_TOKEN in config!")
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()