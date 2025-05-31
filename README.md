# ShadowDaemonBot

ShadowDaemonBot is a dual‐platform bot for Discord and Telegram that provides Shadowrun‐themed dice‐rolling, NPC management, and edition configuration. It uses a MySQL backend to store per‐user and per‐chat settings (e.g. “SR4”, “SR5”, or “SR6”). Both Discord and Telegram adapters share the same core logic for rolling dice pools (with exploding “edge” dice), mapping keyword thresholds (e.g. “easy,” “hard”), and formatting output (Markdown/MarkdownV2).

---

## Table of Contents

1. [Features](#features)
2. [Directory Structure](#directory-structure)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Database Schema](#database-schema)
7. [Running the Bot](#running-the-bot)
8. [Commands & Usage](#commands--usage)
   - [Dice Rolling Commands](#dice-rolling-commands)
   - [Edition Configuration](#edition-configuration)
   - [NPC Management (Telegram Only)](#npc-management-telegram-only)
   - [Help Command](#help-command)
9. [Code Overview](#code-overview)
   1. [Core Modules](#core-modules)
   2. [Platform Adapters](#platform-adapters)
   3. [Utilities](#utilities)
   4. [Configuration](#configuration-module)
   5. [Entry Point](#entry-point)
10. [Troubleshooting](#troubleshooting)
11. [Contributing](#contributing)
12. [License](#license)

---

## Features

- **Dual‐Platform Support**: Runs on both Discord (slash commands) and Telegram (Bot API).
- **Shadowrun Dice Logic**:
  - Rolls a pool of d6s (“Rule of Six” for “edge” dice).
  - Computes hits (5+), net hits against a threshold, glitch/critical glitch, and (for SR5) hit caps.
  - Parses keywords like “easy,” “hard,” “extreme” into numeric thresholds.
- **Per‐User & Per‐Chat Edition Settings**:
  - Supports SR4, SR5, SR6.
  - Default edition is SR5.
  - Users or chat administrators can change the edition via `/ed` (Discord) or `/ed` (Telegram).
- **NPC Management (Telegram Only)**:
  - `/npc_create` to create a new NPC entry (with optional alias, template, “unique” flag, “shared” flag).
  - `/npc_list_templates` to list existing NPC templates.
  - Stored in a MySQL `npcs` table.
- **Centralized Error Reporting**:
  - Errors in Discord or Telegram handlers are logged to stderr (for systemd/hosting) and forwarded to a configured Discord “log channel.”

---

## Directory Structure

```
.
├── pyproject.toml
├── requirements.txt
├── setup.py
│
├── shadowdaemon
    ├── config.py
    ├── run_all_bots.py   ← (duplicated at root for convenience)
    │
    ├── core
    │   ├── db_crud.py
    │   └── dice_roller.py
    │
    ├── platforms
    │   ├── bot_helper.py
    │   ├── discord_bot.py
    │   └── telegram_bot.py
    │
    └── utils
        └── error_handler.py


```

- **Root Files**
  - `.env` – Environment variables (not checked into Git).
  - `pyproject.toml` / `setup.py` / `requirements.txt` – packaging and dependencies.
  - `run_all_bots.py` – Entry point to start both Discord and Telegram bots in parallel.
- **`shadowdaemon/` Package**
  - **`config.py`** – Central configuration (loads environment variables, defines tokens, database credentials, edition defaults, prompts).
  - **`core/`**
    - `db_crud.py` – MySQL connection and CRUD for “users,” “chats,” and NPC templates.
    - `dice_roller.py` – Core dice‐pool parsing and result computation (wave rerolls, hits, net hits, glitches).
  - **`platforms/`**
    - `bot_helper.py` – Formatting routines (Markdown‐escaping, die‐face formatting, line grouping).
    - `discord_bot.py` – Discord slash command adapter.
    - `telegram_bot.py` – Telegram CommandHandler adapter.
  - **`utils/`**
    - `error_handler.py` – Captures exceptions, logs to stderr, and forwards tracebacks to a Discord “log channel.”

---

## Prerequisites

1. **Python 3.10+**
2. **MySQL Server**
   - Create a database (e.g. `shadowdaemon_db`).
   - Grant a user (username/password) appropriate privileges.
3. **Discord Bot Application** (for Discord support)
   - **Discord Bot Token**
4. **Telegram Bot** (for Telegram support)
   - **Telegram Bot Token**
5. **Environment Variables**  
   Create a file named `.env` at the project root (see [Configuration](#configuration)) with the following keys:

   ```ini
   # MySQL Database
   DB_HOST=localhost
   DB_NAME=shadowdaemon_db
   DB_USER=your_db_username
   DB_PASS=your_db_password

   # Discord Bot
   DISCORD_BOT_TOKEN=your_discord_bot_token
   DISCORD_LOG_CHANNEL_ID=<discord-channel-id-for-error-logging>

   # Telegram Bot
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ```

6. **Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   The `requirements.txt` should include (but is not limited to):
   ```
   python-dotenv>=0.20.0
   mysql-connector-python>=8.0.0
   discord.py>=2.0.0
   python-telegram-bot>=20.0
   ```

---

## Installation

1. **Clone the repository**

   ```bash
   git clone git@github.com:scarglamour/ShadowDaemonBot.git
   cd ShadowDaemonBot
   ```

2. **Create & activate a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate      # macOS/Linux
   .\venv\Scripts\activate    # Windows PowerShell
   ```

3. **Install Python dependencies**

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Create your `.env` file**  
   Copy the template below into `.env` (at project root), filling in your credentials:

   ```ini
   # Database credentials
   DB_HOST=localhost
   DB_NAME=shadowDaemon_db
   DB_USER=shadow_user
   DB_PASS=supersecretpassword

   # Discord Bot
   DISCORD_BOT_TOKEN=MzI1OD...your_token_here
   DISCORD_LOG_CHANNEL_ID=123456789012345678

   # Telegram Bot
   TELEGRAM_BOT_TOKEN=987654321:ABC-DEF...xyz
   ```

   - **DB_USER** and **DB_PASS** are used by `shadowdaemon/core/db_crud.py` to connect.
   - **DISCORD_LOG_CHANNEL_ID** is the channel ID where all error tracebacks (from both Discord and Telegram) will be forwarded.

5. **Initialize Database Schema**  
   You must create the following tables in your MySQL database (`shadowDaemon_db` by default). You can adjust column names as desired, but the code expects:

   ```sql
   -- Table for user settings (per‐user SR edition)
   CREATE TABLE IF NOT EXISTS user_settings (
     user_id BIGINT PRIMARY KEY,
     edition VARCHAR(4) NOT NULL
   );

   -- Table for chat settings (per‐chat SR edition)
   CREATE TABLE IF NOT EXISTS chat_settings (
     chat_id BIGINT PRIMARY KEY,
     edition VARCHAR(4) NOT NULL
   );

   -- Table for NPCs
   CREATE TABLE IF NOT EXISTS npcs (
     npc_id        BIGINT AUTO_INCREMENT PRIMARY KEY,
     owner_user_id BIGINT NOT NULL,
     owner_chat_id BIGINT NULL,
     name          VARCHAR(100) NOT NULL,
     alias         VARCHAR(50) NULL UNIQUE,
     template      TINYINT(1) NOT NULL DEFAULT 0,
     is_unique     TINYINT(1) NOT NULL DEFAULT 0,
     shared        TINYINT(1) NOT NULL DEFAULT 0,
     -- Example stat fields (you may adjust types as desired):
     edition             VARCHAR(4) NULL,
     body                INT NULL,
     agility             INT NULL,
     reaction            INT NULL,
     strength            INT NULL,
     willpower           INT NULL,
     logic               INT NULL,
     intuition           INT NULL,
     charisma            INT NULL,
     essence             FLOAT NULL,
     initiative          INT NULL,
     initiative_dice     INT NULL,
     physical_monitor    INT NULL,
     stun_monitor        INT NULL,
     physical_limit      INT NULL,
     mental_limit        INT NULL,
     social_limit        INT NULL,
     armor               INT NULL,
     augmentations       TEXT NULL,
     gear                TEXT NULL,
     abilities           TEXT NULL,
     other               TEXT NULL
   );
   ```

   > **Note:** The `npc_args` clone logic in `db_crud.py` expects columns like `edition`, `body`, `agility`, etc., if you wish to use “template cloning.” Feel free to extend/modify these fields to fit your own NPC schema.

---

## Configuration

All configuration is managed via environment variables (loaded from `.env`). The critical keys are:

- **`DB_HOST`**: MySQL host (default: `localhost`).
- **`DB_NAME`**: MySQL database name (default: `shadowdaemon_db`).
- **`DB_USER`**: Database username.
- **`DB_PASS`**: Database password.
- **`DISCORD_BOT_TOKEN`**: Discord bot token (from Discord Developer Portal).
- **`DISCORD_LOG_CHANNEL_ID`**: Discord channel ID where errors will be posted.
- **`TELEGRAM_BOT_TOKEN`**: Telegram bot token (from BotFather).

`config.py` will raise a `RuntimeError` if `DB_USER`, `DB_PASS`, `DISCORD_BOT_TOKEN`, or `TELEGRAM_BOT_TOKEN` are missing.

---

## Database Schema

1. **`user_settings`**

   - `user_id` (BIGINT, PK) – Telegram user ID or Discord user ID if needed.
   - `edition` (VARCHAR(4)) – One of `SR4`, `SR5`, `SR6`.

2. **`chat_settings`**

   - `chat_id` (BIGINT, PK) – Telegram chat ID or Discord guild ID.
   - `edition` (VARCHAR(4)) – One of `SR4`, `SR5`, `SR6`.

3. **`npcs`**
   - `npc_id` (BIGINT, AUTO_INCREMENT, PK)
   - `owner_user_id` (BIGINT) – Telegram user ID who created this NPC.
   - `owner_chat_id` (BIGINT, NULL) – Telegram chat ID (NULL if private chat).
   - `name` (VARCHAR(100)) – NPC’s display name.
   - `alias` (VARCHAR(50), UNIQUE, NULL) – Optional alias (for cloning/templates).
   - `template` (TINYINT) – 0 or 1 (1 means “this NPC is a template”).
   - `is_unique` (TINYINT) – Boolean flag if the NPC is unique.
   - `shared` (TINYINT) – Boolean flag if the NPC is shared across chats/users.
   - [Optional fields for “cloning” logic:]  
     `edition, body, agility, reaction, strength, willpower, logic, intuition, charisma, essence, initiative, initiative_dice, physical_monitor, stun_monitor, physical_limit, mental_limit, social_limit, armor, augmentations, gear, abilities, other` – All of these columns are used when you “clone” from a template. If you do not plan to use templates, you can omit them or simplify the schema.

---

## Running the Bot

There are two ways to start ShadowDaemonBot:

1. **Run Discord and Telegram bots in parallel** (recommended)

   ```bash
   python run_all_bots.py
   # This spawns DiscordBot in a daemon thread, then starts TelegramBot in the main thread.
   ```

   - Discord bot will log “Discord bot ready as <BotName>” to stdout.
   - Telegram bot will start polling on your chosen port.

2. **Run only Discord or only Telegram**

   - **Discord only**
     ```bash
     cd shadowdaemon
     python -m shadowdaemon.platforms.discord_bot
     ```
   - **Telegram only**
     ```bash
     cd shadowdaemon
     python -m shadowdaemon.platforms.telegram_bot
     ```

---

## Commands & Usage

### Dice Rolling Commands

Both platforms share the same `/r` or `/roll` interface, which rolls a dice pool:

```
/r <dice>[e] [limit] [threshold] [comment]
```

1. **`<dice>`** – Number of D6 to roll (1–99). Add an `e` suffix to roll with “Edge” (exploding Rule of Six):
   - `10` → Roll 10 dice, no edge.
   - `10e` → Roll 10 dice with edge (any 6s generate a new wave of dice).
2. **`[limit]`** – (SR5 only) Optional numeric cap on hits. If omitted, there is no cap.
3. **`[threshold]`** – Target number of hits required for success. Can be:
   - A raw integer: e.g. `3`.
   - For SR5, you can prefix with `t`: e.g. `t2`.
   - A keyword (SR4/SR5 only): `easy`, `average`, `hard`, `veryhard` (SR5 only), `extreme`.
4. **`[comment]`** – Any trailing text is treated as a comment/description (e.g. “Sneaking quietly”).

**Examples**:

- `/r 10`  
  Rolls 10 dice, reports total hits (5 or 6).
- `/r 8e`  
  Rolls 8 dice with edge (exploding 6s).
- `/r 12 6 hard`  
  Rolls 12 dice, cap hits at 6 (SR5), threshold = 4 (hard).
- `/r 8e 4 t2 Sneak in (with edge!)`

#### Output

- **Discord** – Uses bold/underline/strikethrough plus emojis:

  ```
  🎲 SR5 Rolls: (Using edge!)
  __6__ __5__ 4 3 2 1  …

  🏹 **Hits: 5** (capped from 7)
  🎯 Net Hits: 3
  **Success!**
  😵 Critical Glitch! 😵
  ```

- **Telegram** – Uses MarkdownV2 escapes:

  ```
  *📝 "Sneak in (with edge!)"*

  🎲 *SR5 Rolls:*
  __6__ __5__ 4 3 2 1  …

  🏹 __*Hits: 5*__
  _(_(capped from 7!)_)_
  🎯Net Hits: 3
  *Success!*
  💀 Critical Glitch! 💀
  ```

---

### Edition Configuration

- Use `/ed` (Discord slash) or `/ed <edition>` (Telegram) to **view** or **set** the current edition.
  - If you call `/ed` without an argument, the bot replies with usage help (`Allowed: SR4, SR5, SR6`).
  - Valid inputs: `4`, `5`, `6`, `SR4`, `SR5`, `SR6` (case‐insensitive).
  - In **Discord group/guild**, only users with Administrator privileges may change the edition. In **Telegram groups**, only Admin/Creator may change.
  - In a **private** chat (Discord DM or Telegram), any user can run `/ed <edition>` to set their own personal preference.
  - The chosen edition is stored in the `user_settings` (private) or `chat_settings` (group/guild) table.

**Examples**:

- `/ed` ⇒ “Usage: /ed <edition> Allowed: SR4, SR5, SR6”
- `/ed SR6` ⇒ “✅ Edition set to **SR6**”

---

### NPC Management (Telegram Only)

#### `/npc_create <name> [-a alias] [-t template] [-u] [-s]`

- **`<name>`** (required) – Full NPC name (allows spaces).
- **`-a alias`** (optional) – A unique alias (no spaces) used for cloning templates.
- **`-t template`** (optional) – If you supply an existing template‐alias, the new NPC will be cloned from that template (copying over stats).
- **`-u`** (optional flag) – Mark this NPC as **unique** (only one copy exists).
- **`-s`** (optional flag) – Mark this NPC as **shared** (can be used across chats/users).

**Rules**:

- If you run `/npc_create` in a **private chat**, any `-a alias` is dropped (aliases and templates only work in group chats).
- If `-t template` is provided, the code checks that an NPC with `template = 1` and the given alias exists—otherwise it returns an error.
- On success, the bot replies with a summary of the new NPC (ID, name, alias, template, unique/shared flags).

#### `/npc_list_templates`

Lists all NPCs where `template = 1`. The response is a simple “Available NPC Templates” list (name and alias). If no templates exist, replies with “📜 You have no NPC templates available.”

---

### Help Command

- **Discord**: `/help`
- **Telegram**: `/help`

Replies with a multi‐line string containing usage examples, threshold keywords, and dice‐rolling options. The content is defined in `config.py` as `HELP_TEXT`:

```
Usage: /r <dice>[e] [limit] [threshold] [comment]

- <dice>: Number of dice to roll
- [e]: Roll with edge (exploding dice) flag
- [limit]: (SR5 only) Optional limit on hits
- [threshold]: Optional threshold as number (with 't' prefix for SR5) or keyword (SR4/SR5 only)
- [comment]: Optional description

SR 4 Threshold keywords:
- Easy (ea) - 1
- Average (av) - 2
- Hard (ha) - 4
- Extreme (ex) - 6

SR 5 Threshold keywords:
- Easy (ea) - 1
- Average (av) - 2
- Hard (ha) - 4
- Very Hard (vh) - 6
- Extreme (ex) - 8

Examples:
 /r 10
 /r 10 5
 /r 12 6 Hard
 /r 8e 4 t2 Sneaking in (with Edge!)
```

---

## Code Overview

### Core Modules

#### `shadowdaemon/core/db_crud.py`

- **Responsibility**:
  - Creates a MySQL connection (`get_db()`).
  - Initializes default user/chat settings if missing (`init_user_settings`, `init_chat_settings`).
  - `get_user_edition(user_id)` / `get_chat_edition(chat_id)` retrieve the stored edition or create a default row.
  - `set_user_edition(user_id, edition)` / `set_chat_edition(chat_id, edition)` to update the edition.
  - `get_edition(user_id, chat_id, chat_type)` abstracts “private vs. group.”
  - `add_npc(user_id, chat_id, npc_args)` inserts a new NPC record, with optional “cloning from template” logic (copies over stats columns).

#### `shadowdaemon/core/dice_roller.py`

- **Responsibility**:
  - `parse_threshold(keyword, edition)` – Maps difficulty keywords (“easy,” “hard,” etc.) to numeric thresholds for SR4 or SR5.
  - `parse_roll_args(raw_args, edition)` – Parses raw `/r` tokens into `(dice_pool, edge_flag, limit, threshold, comment)`.
  - `roll_dicepool(num_dice, edge)` – Returns a list of “waves” (lists of ints) for a dice pool with optional exploding 6s.
  - `get_roll_results(num_dice, edge, limit, threshold, edition)` – Rolls the dice, counts raw hits (5+) and ones, applies SR5 limit if provided, computes net hits/outcome, and glitch/critical glitch. Returns a dictionary with:
    - `waves` (List[List[int]])
    - `raw_hits` (int)
    - `hits` (int, possibly capped)
    - `limit` (int or None)
    - `net_hits` (int or None)
    - `outcome` (string)
    - `glitch` (string or empty)

### Platform Adapters

#### `shadowdaemon/platforms/bot_helper.py`

- **Responsibility**: Shared formatting for Discord and Telegram.
  - `format_die_discord(d: int) → str` – Underlines (5/6) or strikethrough (1) for Discord.
  - `format_die_telegram(d: int) → str` – Underlines (5/6) or single‐tilde (1) for Telegram MarkdownV2.
  - `group_into_lines(tokens, per_line, spacer_every) → List[str]` – Splits a long list of dice strings into lines.
  - `format_for_discord(data, edition, edge, comment) → str` – Builds a Discord‐friendly multi‐line string (with bold, underline, emojis).
  - `format_for_telegram(data, edition, edge, comment) → str` – Builds a Telegram‐friendly MarkdownV2 string (escapes special chars).
  - `markdown_escape_telegram(text) → str` – Escapes all MarkdownV2‐reserved characters.
  - `parse_npc_create_telegram(args_text) → dict` – Parses `name`, `-a alias`, `-t template`, `-u`, `-s` flags from a `/npc_create` raw string.

#### `shadowdaemon/platforms/discord_bot.py`

- **Responsibility**: Connect to Discord via `discord.py` (v2.x), register slash commands, dispatch to core logic, format replies with `bot_helper`.
- **Key Components**:
  - `ShadowDaemonBot(commands.Bot)` – Subclass that syncs slash commands on startup.
  - `@bot.tree.command(name="help", ...)` – Sends `HELP_TEXT` (ephemeral).
  - `@bot.tree.command(name="r", ...)` & `@bot.tree.command(name="roll", ...)` – Both call `do_roll(interaction, expression)`.
  - `do_roll(...)` – Parses user/edition context, calls `parse_roll_args`, `get_roll_results`, then `format_for_discord` and sends the response. Catches `ValueError` for bad usage, or other exceptions for error reporting.
  - `@bot.tree.command(name="ed", ...)` – View/set edition. Checks if user is guild admin before persisting new edition.
  - `@bot.tree.command(name="start", ...)` – In DMs, initializes default edition and responds.
  - **Error Handling**: In `except Exception as e`, calls `report_discord_error(bot, interaction, command_name, e)`.

#### `shadowdaemon/platforms/telegram_bot.py`

- **Responsibility**: Connect to Telegram via `python-telegram-bot` v20 (asyncio), register CommandHandlers, dispatch to core logic, format replies with `bot_helper`.
- **Key Components**:
  - `bot_added` (ChatMemberHandler) – Fired when the bot is added to a new chat. Initializes edition and sends a greeting.
  - `npc_create_command` (CommandHandler for `/npc_create`) – Parses arguments with `parse_npc_create_telegram`, validates template existence (if provided), calls `add_npc()`, and replies with a summary. Catches exceptions and calls `report_telegram_error`.
  - `npc_list_templates` – Queries all `npcs WHERE template=1`. Replies with a list or “no templates.”
  - `help_command` – Replies with `HELP_TEXT`.
  - `roll_dice_command` (CommandHandler for `/r` and `/roll`) – Similar to Discord: determine edition, parse arguments, roll, and reply with `format_for_telegram`.
  - `set_edition_command` (CommandHandler for `/ed`) – Validates user is admin in group (or always allowed in private), persists new edition, and replies.
  - `start_command` – Initializes or fetches user’s edition and replies in private chats.
  - **Error Handling**: In each `except`, sets `context.error = e`, then calls `report_telegram_error(update, context)`.

### Utilities

#### `shadowdaemon/utils/error_handler.py`

- **Responsibility**: Centralized error logging and forwarding to Discord.
- **Functions**:
  - `report_discord_error(bot_client, interaction, command_name, error)`
    1. Formats a Python `traceback.format_exc()`.
    2. Logs to stderr (systemd, Docker logs, etc.).
    3. Sends an `Embed` to the channel ID defined by `DISCORD_LOG_CHANNEL_ID`. If the traceback exceeds Discord’s 1024‐character limit per field, it automatically chunks it.
  - `report_telegram_error(update, context)`
    1. Takes `context.error` (the actual exception) and full traceback.
    2. Logs to stderr.
    3. Uses the imported `discord_bot` instance’s event loop to schedule a Discord‐embed message to the same `DISCORD_LOG_CHANNEL_ID`, chunking the traceback every 1024 characters.

### Configuration Module

#### `shadowdaemon/config.py`

- Loads environment variables with `dotenv.load_dotenv()`.
- Reads:
  - `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS` – Missing `DB_USER` or `DB_PASS` raises `RuntimeError`.
  - `RAW_ALLOWED`, `ALLOWED_EDITIONS`, `DEFAULT_EDITION` – Edition constants.
  - `BOT_USAGE_PROMPT`, `DICE_NUMBER_ERROR`, `HELP_TEXT` – Strings for usage prompts and help text.
  - `BASE_DIR` (project root path), `MAX_COMMENT_LENGTH`, `MAX_DICE` (upper limit).
  - `TELEGRAM_TOKEN`, `DISCORD_TOKEN` – Missing either throws `RuntimeError`.
  - `DISCORD_TEST_GUILD_ID`, `DISCORD_LOG_CHANNEL_ID` – IDs for testing and error logging.

### Entry Point

#### `run_all_bots.py` (root)

- Imports `run_telegram()` and `run_discord()` from the respective platform adapters.
- Spawns a daemon thread for the Discord bot (`threading.Thread(target=run_discord, daemon=True).start()`).
- Calls `run_telegram()` in the main thread so the process remains alive.

---

## Troubleshooting

1. **Missing Environment Variables**

   - If you see `RuntimeError: Missing DISCORD_BOT_TOKEN`, make sure `.env` contains `DISCORD_BOT_TOKEN=…`.
   - Similarly for `TELEGRAM_BOT_TOKEN`, `DB_USER`, and `DB_PASS`.

2. **Database Connection Errors**
   - Confirm MySQL is running and credentials in `.env` are correct.
   - Verify your `user_settings` and `chat_settings` tables exist.
   - Use a MySQL client to test:
     ```bash
     mysql -u $DB_USER -p -h $DB_HOST
     USE $DB_NAME;
     SHOW TABLES;
     ```
3. **Discord Slash Commands Not Appearing**

   - Make sure your bot’s “Application ID” is invited to the guild with `applications.commands` scope.
   - Ensure you have called `await self.tree.sync()` in `ShadowDaemonBot.setup_hook()`.
   - If testing in a single server, uncomment and configure the `DISCORD_TEST_GUILD_ID` lines, then run in “developer mode.”

4. **Telegram Bot Not Responding**

   - Confirm the token in `.env` is correct and not revoked.
   - Ensure you started polling (i.e. `app.run_polling()`).
   - Make sure the machine or container has outbound internet access to Telegram’s API.

5. **Error Tracebacks Not Appearing in Discord**

   - Check that `DISCORD_LOG_CHANNEL_ID` is a valid channel where the bot can post messages.
   - Verify the bot has “Send Messages” permissions in that channel.
   - Confirm the `error_handler` module is not crashing itself (inspect logs for “Failed to schedule error-report”).

6. **Line Endings / Encoding Issues**
   - On Windows: If you see “LF will be replaced by CRLF” warnings, configure Git’s `core.autocrlf` or add a `.gitattributes` to normalize line endings.

---

## Contributing

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Make your changes**
5. **Run tests / manual checks**
   - (At present, there are no automated tests. You can spin up a local MySQL + test bot on Discord/Telegram to verify.)
6. **Commit & push**
   ```bash
   git add .
   git commit -m "Add feature: <description>"
   git push origin feature/my-new-feature
   ```
7. **Open a Pull Request**

Please ensure that:

- Any added dependencies are reflected in `requirements.txt`.
- Code follows PEP-8 styling (you may use `black` or `flake8`).
- You update this `README.md` if you add new commands/configuration.

---

## License

```
MIT License

Copyright (c) 2024 ScarGlamour

```

---

### Contact / Support

- **Issues & Bug Reports**: [GitHub Issues](https://github.com/scarglamour/ShadowDaemonBot/issues)
- **Discussions / Feature Requests**: [GitHub Discussions](https://github.com/scarglamour/ShadowDaemonBot/discussions)

If any details are missing (e.g., database migration scripts, additional commands, or environment specifics), please open an Issue or reach out via DM. Enjoy running ShadowDaemonBot!
