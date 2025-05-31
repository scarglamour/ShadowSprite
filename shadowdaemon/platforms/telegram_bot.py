"""
platforms/telegram_bot.py

Telegram adapter for the ShadowDaemon bot.
Handles incoming Telegram updates and commands, delegates to core logic, and formats responses
using MarkdownV2. Includes handlers for:
  - bot_added: when the bot joins a new chat
  - help_command: responding to /help
  - roll_handler: processing /r dice rolls
  - start_command: responding to /start in private chats
  - main: bootstrapping the bot
"""
import logging
from typing import Any, Dict, Literal, cast
from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder,
    CallbackContext,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
)
from shadowdaemon.config import (
    TELEGRAM_TOKEN,
    ALLOWED_EDITIONS,
    RAW_ALLOWED,
    BOT_USAGE_PROMPT,
    HELP_TEXT,
)
from shadowdaemon.core.db_crud import (
    add_npc,
    get_edition,
    get_chat_edition,
    set_edition,
    get_db
)
from shadowdaemon.core.dice_roller import parse_roll_args, get_roll_results
from shadowdaemon.platforms.bot_helper import (
    format_for_telegram, 
    parse_npc_create_telegram,
    markdown_escape_telegram
)
from shadowdaemon.utils.error_handler import report_telegram_error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def bot_added(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler invoked when the bot is added to a group or channel.
    Initializes chat settings and sends a greeting message with current edition.

    Args:
        update (Update): The update containing old and new ChatMember states.
        context (ContextTypes.DEFAULT_TYPE): Context with bot instance and helpers.
    """
    if update.my_chat_member is not None:
        old, new = update.my_chat_member.old_chat_member, update.my_chat_member.new_chat_member
        if (
            new.user.id == context.bot.id
            and old.status in (ChatMember.LEFT, ChatMember.BANNED)
            and new.status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR)
        ):
            chat = update.effective_chat
            if chat is not None:
                edition = get_chat_edition(chat.id)
                await context.bot.send_message(
                    chat.id,
                    f"Hello! I’ve initialized this chat’s settings to {edition} edition.\n"
                    f"Use /ed <edition> to change this setting."
                )

from telegram import Update
from telegram.ext import CallbackContext


async def npc_create_command(update: Update, context: CallbackContext):
    logger.info("🔔 npc_create_command invoked: text=%r", update.message and update.message.text)
    # Only handle real message updates
    if update.message is None or update.message.text is None:
        return
    try:
        full_text = update.message.text
        command_prefix = '/npc_create'
        if not full_text.startswith(command_prefix):
            await update.message.reply_text("Command should start with /npc_create.")
            return
        args_text = full_text[len(command_prefix):].strip()
        if not args_text:
            await update.message.reply_text(
                "Usage: /npc_create <name> [-a alias] [-t template] [-u] [-s]"
            )
            return
        # 1) Parse out name, alias, template, flags
        npc_args = parse_npc_create_telegram(args_text)
        # 2) Validate name
        if not npc_args.get('name'):
            return await update.message.reply_text("Please specify the NPC name.")
        # 3) Detect private chat and drop alias if needed
        chat = update.effective_chat
        alias_dropped = None
        if chat and chat.type == 'private' and npc_args.get('alias'):
            alias_dropped = npc_args['alias']
            npc_args['alias'] = None
        # 3.1) If template alias check passed, verify it exists
        tmpl_alias = npc_args.get('template')
        if tmpl_alias:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "SELECT 1 FROM npcs WHERE alias = %s AND template = 1",
                (tmpl_alias,)
            )
            if cur.fetchone() is None:
                # no such template!
                return await update.message.reply_text(
                    f"❌ Template alias `{tmpl_alias}` not found. "
                    "Use `/npc_list_templates` to see the available templates.",
                    parse_mode="MarkdownV2"
                )
        # 4) Insert into DB (chat_id=None in private chats)
        user = update.effective_user
        if not user:
            return await update.message.reply_text("Could not identify you—please try again.")
        if chat is None:
            return await update.message.reply_text(
                "⚠️  Could not determine chat context; NPC creation requires a chat or channel."
            )
        db_chat_id = None if chat.type == 'private' else chat.id
        new_id = add_npc(
            user_id=user.id,
            chat_id=db_chat_id,
            npc_args=npc_args
        )
        # 5) Build confirmation
        safe = markdown_escape_telegram
        lines = [
            f"✅ Created NPC #{new_id}:",
            f"• Name: {safe(npc_args['name'])}",
            f"• Alias: {safe(npc_args['alias'] or 'none')}",
            f"• Template: {safe(npc_args['template'] or 'none')}",
            f"• Unique: {'yes' if npc_args['is_unique'] else 'no'}",
            f"• Shared: {'yes' if npc_args['shared'] else 'no'}",
        ]
        if alias_dropped:
            lines.append(
                f"⚠️  I dropped alias `{safe(alias_dropped)}` because aliases only work in group/supergroup chats."
            )
        # 6) Send it back
        await update.message.reply_text('\n'.join(lines), parse_mode="MarkdownV2")
    except Exception as e:
        context.error = e
        await report_telegram_error(update, context)
        if update.message:
            await update.message.reply_text("⚠️ Something went wrong, the Maker has been notified.")


async def npc_list_templates(update: Update, context: CallbackContext):
    # Only handle real messages
    if update.message is None:
        return

    user = update.effective_user
    chat = update.effective_chat
    user_id = user.id if user else None
    # For private chats we only show the user's own templates
    chat_id = chat.id if chat and chat.type != 'private' else None

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(
        """
        SELECT name, alias
          FROM npcs
         WHERE template = 1
        """
    )
    rows_raw = cur.fetchall()    # type: list[Any]
    rows: list[Dict[str, Any]] = [cast(Dict[str, Any], r) for r in rows_raw]

    if not rows:
        return await update.message.reply_text("📜 You have no NPC templates available.")

    safe = markdown_escape_telegram
    lines = ["📜 *Available NPC Templates:*"]
    for row in rows:
        name  = row["name"]
        alias = row["alias"] if row["alias"] else "(none)"
        lines.append(safe(f"• {name} (alias: {alias})"))

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="MarkdownV2"
    )


async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /help command.
    Sends the standardized help text to the user.

    Args:
        update (Update): The incoming help command update.
        context (ContextTypes.DEFAULT_TYPE): Context object (unused).
    """
    if update.message is not None:
        await update.message.reply_text(HELP_TEXT)


async def roll_dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /r command to roll dice.
    Parses arguments, invokes core roller, and formats the result for Telegram.

    Workflow:
      1. Determine user/chat edition via get_edition.
      2. Parse dice pool, edge, limit, threshold, and comment.
      3. Compute roll results via get_roll_results.
      4. Format the reply with format_for_telegram.
      5. Send the reply as MarkdownV2.

    Args:
        update (Update): The update containing the /r command.
        context (ContextTypes.DEFAULT_TYPE): Context with command arguments.

    Raises:
        ValueError: If argument parsing fails, triggers usage prompt.
    """
    user = update.effective_user
    chat = update.effective_chat
    if user is not None and chat is not None:
        edition = get_edition(user.id, chat.id, cast(Literal['private', 'group', 'supergroup', 'channel'], chat.type))
        if update.message is not None and context is not None:
            try:
                dice, edge, limit, threshold, comment = parse_roll_args(context.args or [], edition)
                result_data = get_roll_results(dice, edge, limit, threshold, edition)
                result_text = format_for_telegram(result_data, edition, edge, comment)
                await update.message.reply_text(result_text, parse_mode="MarkdownV2")
            except ValueError:
                return await update.message.reply_text(BOT_USAGE_PROMPT)
            except Exception as e:
                context.error = e
                await report_telegram_error(update, context)
                if update.message:
                    await update.message.reply_text("⚠️ Something went wrong, the Maker has been notified.")


async def set_edition_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /ed — parses the requested edition, enforces permissions,
    calls db_crud.set_edition, and confirms back to the user or group.
    """
    if update.message is not None:
        # 1) Validate usage
        if not context.args:
            return await update.message.reply_text(
                f"Usage: /ed <edition>\nAllowed: {ALLOWED_EDITIONS}"
            )
        # 2) Normalize and validate edition token
        inp = context.args[0].upper()
        if inp not in RAW_ALLOWED:
            return await update.message.reply_text(
                f"Invalid edition. Choose from: {ALLOWED_EDITIONS}"
            )
        edition = inp if inp.startswith("SR") else f"SR{inp}"
        if update.effective_user is not None:
            user_id = update.effective_user.id
            chat = update.effective_chat
            if chat is not None:
                # 3) In groups, only admins/creators may change the setting
                if chat.type != "private":
                    member = await context.bot.get_chat_member(chat.id, user_id)
                    if member.status not in ("administrator", "creator"):
                        return await update.message.reply_text(
                            "❌ Only group admins can change the edition here."
                        )
                # 4) Persist the new setting
                set_edition(
                    user_id=user_id,
                    chat_id=chat.id,
                    chat_type=cast(Literal['private', 'group', 'supergroup', 'channel'], chat.type),
                    edition=edition
                )
                # 5) Send confirmation
                if chat.type == "private":
                    await update.message.reply_text(f"✅ Your edition is now set to {edition}.")
                else:
                    await update.message.reply_text(f"✅ This chat’s edition is now set to {edition}.")


async def start_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /start command in private chat.
    Initializes or fetches user's edition setting and sends a welcome message.

    Args:
        update (Update): The update containing the /start command.
        context (ContextTypes.DEFAULT_TYPE): Context with bot instance.
    """
    user = update.effective_user
    chat = update.effective_chat
    if user is not None and chat is not None and update.message is not None:
        edition = get_edition(user.id, chat.id, cast(Literal['private', 'group', 'supergroup', 'channel'], chat.type))

        if chat.type == "private":
            await update.message.reply_text(
                f"Welcome! Your user settings have been initialized to {edition} edition.\n"
                "Use /ed <edition> to change this setting."
            )
        else:
            await update.message.reply_text("Use me in a private chat with /start!")


def main():
    """
    Entry point that starts the Telegram bot.
    Registers command and chat-member handlers, then begins polling.

    Raises:
        ValueError: If TELEGRAM_TOKEN is not set in environment.
    """
    if not TELEGRAM_TOKEN:
        raise ValueError("Missing SHADOWDAEMON_TOKEN environment variable!")
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .build()
    )
    # Error log tester
    async def boom(update, context):
        logger.info("🔔 boom handler triggered by user %s", update.effective_user.id)
        raise RuntimeError("💥 test error")
    app.add_handler(CommandHandler("boom", boom))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ed", set_edition_command))
    app.add_handler(CommandHandler("npc_create", npc_create_command))
    app.add_handler(CommandHandler("npc_list_templates", npc_list_templates))
    app.add_handler(CommandHandler(["r", "roll"], roll_dice_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(ChatMemberHandler(bot_added, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_error_handler(report_telegram_error)
    app.run_polling()

if __name__ == "__main__":
    main()