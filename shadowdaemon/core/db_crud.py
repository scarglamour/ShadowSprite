"""
core/db_crud.py

Database connection and CRUD operations for user and chat settings.
These functions handle initializing default settings and getting/setting
Shadowrun edition preferences for users and chats.
"""
import mysql.connector
from typing import Any, Dict, Literal, Optional, cast
from shadowdaemon.config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DEFAULT_EDITION

def get_db():
    """
    Create and return a new MySQL database connection using configuration.

    Returns:
        mysql.connector.connection.MySQLConnection: A new database connection.
    """
    return mysql.connector.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def add_npc(
    user_id: int,
    chat_id: Optional[int],
    npc_args: Dict[str, Any]
) -> int:
    """
    Inserts a new NPC, optionally cloning from a template alias.
    :param user_id:  Telegram user id who owns this NPC
    :param chat_id:  Telegram chat id (None for private)
    :param npc_args: {
        'name': str,
        'alias': Optional[str],
        'template': Optional[str],  # alias of a template to clone
        'is_unique': bool,
        'shared': bool
    }
    :returns: new npc_id
    """
    db = get_db()
    cur = db.cursor(dictionary=True)
    tmpl_alias = npc_args.get('template')
    if tmpl_alias:
        # 1) Fetch the template row
        cur.execute(
            "SELECT * FROM npcs WHERE alias = %s AND template = 1",
            (tmpl_alias,)
        )
        template_row_raw = cur.fetchone()
        if not template_row_raw:
            raise ValueError(f"No template found with alias '{tmpl_alias}'")

        template_row: Dict[str, Any] = cast(Dict[str, Any], template_row_raw)
        # 2) Prepare the data to clone
        # List all columns you want to carry over from the template:
        clone_cols = [
            'edition',           # example columns...
            'body','agility','reaction','strength','willpower',
            'logic','intuition','charisma','essence',
            'initiative','initiative_dice','physical_monitor',
            'stun_monitor','physical_limit','mental_limit',
            'social_limit','armor',
            'augmentations','gear','abilities','other'
        ]
        # Build the INSERT column list and values
        cols = ['owner_user_id','owner_chat_id','name','alias','template','is_unique','shared'] + clone_cols
        vals = [
            user_id,
            chat_id,
            npc_args['name'],
            npc_args.get('alias'),
            0,                                        # new NPC is not itself a template
            1 if npc_args.get('is_unique') else 0,
            1 if npc_args.get('shared') else 0,
        ] + [ template_row[col] for col in clone_cols ]

    else:
        # No template: insert only the minimal fields
        cols = [
            'owner_user_id','owner_chat_id','name','alias',
            'template','is_unique','shared'
        ]
        vals = [
            user_id,
            chat_id,
            npc_args['name'],
            npc_args.get('alias'),
            0,  # template flag off
            1 if npc_args.get('is_unique') else 0,
            1 if npc_args.get('shared') else 0
        ]

    # 3) Build and execute the INSERT
    col_sql = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(vals))
    sql = f"INSERT INTO npcs ({col_sql}) VALUES ({placeholders})"
    cur.execute(sql, vals)
    db.commit()

    # 4) Return the new npc_id
    new_id = cur.lastrowid
    assert new_id is not None, "Failed to retrieve new NPC ID"
    return new_id

def init_user_settings(user_id: int) -> None:
    """
    Ensure a default user_settings row exists for the given user.
    Inserts a record with default edition 'SR5' if none exists.

    Args:
        user_id (int): Telegram user ID to initialize settings for.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO user_settings (user_id, edition)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE user_id = user_id
        """, 
        (user_id, DEFAULT_EDITION))
    db.commit()
    cur.close()
    db.close()

def init_chat_settings(chat_id: int) -> None:
    """
    Ensure a default chat_settings row exists for the given chat.
    Inserts a record with default edition 'SR5' if none exists.

    Args:
        chat_id (int): Telegram chat ID to initialize settings for.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO chat_settings (chat_id, edition)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE chat_id = chat_id
        """, 
        (chat_id, DEFAULT_EDITION))
    db.commit()
    cur.close()
    db.close()

def get_user_edition(user_id: int) -> str:
    """
    Retrieve the stored edition for a user, inserting a default if missing.

    Args:
        user_id (int): Telegram user ID.

    Returns:
        str: The user's preferred Shadowrun edition (e.g. 'SR5').
    """
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT edition FROM user_settings WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    db.close()
    if row:
        edition = cast(dict[str, Any], row)['edition']
        return edition
    
    # Initialize default if not found
    init_user_settings(user_id)
    return DEFAULT_EDITION

def get_chat_edition(chat_id: int) -> str:
    """
    Retrieve the stored edition for a chat, inserting a default if missing.

    Args:
        chat_id (int): Telegram chat or group ID.

    Returns:
        str: The chat's preferred Shadowrun edition (e.g. 'SR5').
    """
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT edition FROM chat_settings WHERE chat_id = %s", (chat_id,))
    row = cur.fetchone()
    cur.close()
    db.close()
    if row:
        edition = cast(dict[str, Any], row)['edition']
        return edition
    
    # Initialize default if not found
    init_chat_settings(chat_id)
    return DEFAULT_EDITION

def set_user_edition(user_id: int, edition: str) -> None:
    """
    Create or update a user's preferred edition in the database.

    Args:
        user_id (int): Telegram user ID.
        edition (str): Shadowrun edition code (e.g. 'SR5').
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO user_settings (user_id, edition)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE edition = VALUES(edition)
        """,
        (user_id, edition)
    )
    db.commit()
    cur.close()
    db.close()

def set_chat_edition(chat_id: int, edition: str) -> None:
    """
    Create or update a chat's preferred edition in the database.

    Args:
        chat_id (int): Telegram chat or group ID.
        edition (str): Shadowrun edition code (e.g. 'SR5').
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO chat_settings (chat_id, edition)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE edition = VALUES(edition)
        """,
        (chat_id, edition)
    )
    db.commit()
    cur.close()
    db.close()

def get_edition(
    user_id: int,
    chat_id: int,
    chat_type: Literal['private','group','supergroup','channel']
) -> str:
    """
    Retrieve the preferred edition for a user or chat, auto-initializing if missing.

    Args:
        user_id (int): Telegram user ID.
        chat_id (int): Telegram chat ID.
        chat_type (str): Type of chat ('private', 'group', etc.).

    Returns:
        str: The appropriate Shadowrun edition.
    """
    if chat_type == 'private':
        return get_user_edition(user_id)
    else:
        return get_chat_edition(chat_id)

def set_edition(
    user_id: int,
    chat_id: int,
    chat_type: Literal["private", "group", "supergroup", "channel"],
    edition: str
) -> None:
    """
    Set the preferred edition for a user or chat in the database.

    Args:
        user_id (int): Telegram user ID.
        chat_id (int): Telegram chat ID.
        chat_type (str): Type of chat ('private', 'group', etc.).
        edition (str): Shadowrun edition code (e.g. 'SR5').
    """
    if chat_type == "private":
        set_user_edition(user_id, edition)
    else:
        set_chat_edition(chat_id, edition)