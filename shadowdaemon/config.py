"""
config.py

Centralized configuration for ShadowDaemon:

– Loads environment variables (bot token, database credentials)
– Defines default constants (editions, usage prompts, limits)
– Holds file paths and other global settings
"""
import os
from dotenv import load_dotenv
load_dotenv()   # <-- reads .env into os.environ
from pathlib import Path


# ── Database ────────────────────────────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "shadowdaemon_db")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
if not DB_USER or not DB_PASS:
    raise RuntimeError("Missing DB_USER or DB_PASS")


# ── Editions ────────────────────────────────────────────────────────────────
RAW_ALLOWED = {"4", "5", "6", "SR4", "SR5", "SR6"}
ALLOWED_EDITIONS = "SR4, SR5, SR6 (or drop the SR prefix)"
DEFAULT_EDITION = "SR5"

# ── Message Strings ─────────────────────────────────────────────────────────
BOT_USAGE_PROMPT = "Usage: /r <dice>[e] [limit] [threshold] [comment]"
DICE_NUMBER_ERROR = "Number of dice must be between 1 and 99."
HELP_TEXT = ("Usage: /r <dice>[e] [limit] [threshold] [comment]\n\n"
             "- <dice>: Number of dice to roll\n"
             "- [e]: Roll with edge (exploding dice) flag\n"
             "- [limit]: (SR5 only) Optional limit on hits\n"
             "- [threshold]: Optional threshold as number (with 't' prefix for SR5) or keyword (SR4/SR5 only)\n"
             "- [comment]: Optional description\n\n"
             "SR 4 Threshold keywords:\n"
             "- Easy (ea) - 1\n"
             "- Average (av) - 2\n"
             "- Hard (ha) - 4\n"
             "- Extreme (ex) - 6\n\n"
             "SR 5 Threshold keywords:\n"
             "- Easy (ea) - 1\n"
             "- Average (av) - 2\n"
             "- Hard (ha) - 4\n"
             "- Very Hard (vh) - 6\n"
             "- Extreme (ex) - 8\n\n"
             "Examples:\n"
             "/r 10\n"
             "/r 10 5\n"
             "/r 12 6 Hard\n"
             "/r 8e 4 t2 Sneaking in (with Edge!)"
)

# ── Paths & Other Constants ─────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
MAX_COMMENT_LENGTH = 50
MAX_DICE = 99


# ── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")

# ── Discord ─────────────────────────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_BOT_TOKEN environment variable")
DISCORD_TEST_GUILD_ID = "1337320915897421866"
DISCORD_LOG_CHANNEL_ID = "1367768041198456872"