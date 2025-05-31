"""
platforms/bot_helper.py

Helper functions for formatting Discord & Telegram bot output.
Includes MarkdownV2 escaping, die formatting, line grouping, and full response formatting.
"""

import re
from typing import Dict, Any, List
from shadowdaemon.config import BOT_USAGE_PROMPT


def discord_send_error(ctx, message=BOT_USAGE_PROMPT):
    return ctx.send(f"❌ {message}")


def format_die_discord(d: int) -> str:
    """
    Format a single die face value for Discord output.

    Args:
        d: Integer result of a six-sided die (1 through 6).

    Returns:
        A string token where:
          - Hits (5 or 6) are underlined using (e.g. '__6__').
          - Ones are struck through (e.g. '~~1~~').
          - All other results are plain text.
    """
    if d >= 5:
        return f"__{d}__"
    if d == 1:
        return f"~~{d}~~"
    return str(d)


def format_die_telegram(d: int) -> str:
    """
    Format a single die face value for Telegram output.

    Args:
        d: Integer result of a six-sided die (1 through 6).

    Returns:
        A string token where:
          - Hits (5 or 6) are underlined using MarkdownV2 (e.g. '__6__').
          - Ones are struck through (e.g. '~1~').
          - All other results are plain text.
    """
    if d >= 5:
        return f"__{d}__"
    if d == 1:
        return f"~{d}~"
    return str(d)


def group_into_lines(
    tokens: List[str],
    per_line: int = 10,
    spacer_every: int = 5
) -> List[str]:
    """
    Group a flat list of formatted die tokens into readable lines.

    Args:
        tokens:       List of formatted die strings (e.g. ['__6__','4','~~1~~',...]).
        per_line:     Maximum number of dice tokens per line before wrapping.
        spacer_every: After every this many tokens, insert extra spaces for readability.

    Returns:
        A list of line strings, each containing up to `per_line` tokens,
        with a visual spacer every `spacer_every` tokens.
    """
    lines: List[str] = []
    line = ""

    for i, tok in enumerate(tokens):
        # insert a visual spacer after every `spacer_every` tokens
        if i > 0 and i % spacer_every == 0:
            line += "   "
        # append this token and a space
        line += tok + " "
        # if we've reached `per_line` tokens, commit this line
        if (i + 1) % per_line == 0:
            lines.append(line.strip())
            line = ""
    # any remaining tokens go on a final line
    if line:
        lines.append(line.strip())
    return lines


def format_for_discord(data, edition: str, edge: bool, comment: str) -> str:
    """
    Build a Discord-friendly string from roll data:
      • Optional user comment
      • Edition header with edge flag
      • One line per wave, dice sorted descending
      • Hits, net hits/outcome, glitches
    """
    parts = []

    # 1) Optional comment
    if comment:
        parts.append(f"📝 \"{comment}\"\n")

    # 2) Header with edition & edge tag
    header = f"🎲 {edition} Rolls:"
    if edge:
        header += " *(Using edge!)*"
    parts.append(header)

    # 3) Roll waves formatted into blocks
    wave_blocks = []
    for wave in data["waves"]:
        # sort descending and format each die
        tokens = [format_die_discord(d) for d in sorted(wave, reverse=True)]
        # group into readable lines
        lines = group_into_lines(tokens)
        wave_blocks.append("\n".join(lines))
    parts.append("\n\n".join(wave_blocks)+ "\n")

    # 4) Hits (SR5: show if limit was reached)
    hits = data["hits"]
    raw = data["raw_hits"]
    if data.get("limit") and raw > hits:
        parts.append(f"🏹 **Hits: {hits}** (capped from {raw})\n")
    else:
        parts.append(f"🏹 **Hits: {hits}**\n")

    # 5) Net Hits & outcome (if threshold was used)
    if data.get("net_hits") is not None:
        parts.append(f"🎯 Net Hits: {data['net_hits']}\n")
        parts.append(f"**{data.get('outcome','')}**\n")

    # 6) Glitch / Critical Glitch
    glitch = data.get("glitch")
    if glitch:
        emoji = "💀" if "Critical" in glitch else "😵"
        parts.append(f"{emoji}  {glitch}!  {emoji}")

    # join all with newlines
    return "\n".join(parts)


def format_for_telegram(
    data: Dict[str, Any],
    edition: str,
    edge: bool,
    comment: str
) -> str:
    """
    Build a Telegram‐formatted MarkdownV2 string from the roll data.

    Args:
        data:   Output of roll_dice_command, with keys:
                  - "waves": List[List[int]]
                  - "hits": int
                  - "net_hits": Optional[int]
                  - "outcome": str
                  - "glitch": Optional[str]
        edition:  "SR4" / "SR5" / "SR6"
        edge:     True if edge-exploding was used
        comment:  Optional user comment (raw, unescaped)
    Returns:
        A single MarkdownV2-escaped string ready for telegram.Bot.send_message().
    """
    parts = []
    
    # 1) Optional comment
    if comment:
        parts.append(f"*📝 \"{markdown_escape_telegram(comment)}\"*\n")
    
    # 2) Header with edition & edge tag
    header = f"🎲 *{edition} Rolls:*"
    if edge:
        header += f" {markdown_escape_telegram('(Using edge!)')}"
    parts.append(header)
   
    # 3) Roll waves formatted into blocks
    wave_blocks = []
    for wave in data["waves"]:
        # sort descending and format each die
        tokens = [format_die_telegram(d) for d in sorted(wave, reverse=True)]
        # group into readable lines
        lines = group_into_lines(tokens)
        wave_blocks.append("\n".join(lines))
    parts.append("\n\n".join(wave_blocks))
    
    # 4) Hits
    hits = data["hits"]
    raw = data["raw_hits"]
    if data.get("limit") and raw > hits:
        parts.append(f"🏹 __*Hits: {hits}*__\n _{markdown_escape_telegram(f"(capped from {raw}!)")}_")
    else:
        parts.append(f"🏹 __*Hits: {hits}*__")

    # 5) Net Hits & outcome (if threshold was used)
    if data.get("net_hits") is not None:
        parts.append(markdown_escape_telegram(f"🎯Net Hits: {data['net_hits']}"))
        parts.append(f"*{markdown_escape_telegram(data.get('outcome', ''))}*")

    # 6) Glitch / Critical Glitch
    glitch_message = data.get("glitch")      # e.g. "Glitch" or "Critical Glitch"
    if glitch_message:
        # Pick the right emoji
        emoji = "💀" if "Critical" in glitch_message else "😵"
        # Build the full raw text, including the "!" suffix
        raw = f"{emoji} {glitch_message + '!'} {emoji}"
        # Escape *everything* (emoji are untouched, hyphens etc. get backslashes)
        parts.append(markdown_escape_telegram(raw))

    # join all with newlines
    return "\n\n".join(parts)


def markdown_escape_telegram(text):
    """
    Escape special characters in text for Telegram MarkdownV2.

    Args:
        text: The raw text string to escape.

    Returns:
        A new string with all MarkdownV2-reserved characters backslash-escaped.
    """
    escape_chars = r"\_*[]()~`>#+-=|{}.! "
    return ''.join(f"\\{c}" if c in escape_chars else c for c in text)


def parse_npc_create_telegram(args_text: str) -> dict:
    """
    Parses a /npc_create command for Telegram with options:
    - name (multi-word, required)
    - alias (optional, -a ALIAS)
    - template (optional, -t TEMPLATE)
    - is_unique (optional flag, -u)
    - shared (optional flag, -s)
    Returns a dictionary with parsed fields.
    """
    # Default values
    alias = None
    template = None
    is_unique = False
    shared = False

    # Patterns for -a alias and -t template
    alias_match = re.search(r'-a\s+(\S+)', args_text)
    if alias_match:
        alias = alias_match.group(1)
        # Remove the matched alias argument from text
        args_text = args_text[:alias_match.start()] + args_text[alias_match.end():]

    template_match = re.search(r'-t\s+(\S+)', args_text)
    if template_match:
        template = template_match.group(1)
        # Remove the matched template argument from text
        args_text = args_text[:template_match.start()] + args_text[template_match.end():]

    # Check for -u and -s flags
    if re.search(r'(\s|^)-u(\s|$)', args_text):
        is_unique = True
        # Remove -u flag
        args_text = re.sub(r'(\s|^)-u(\s|$)', ' ', args_text)

    if re.search(r'(\s|^)-s(\s|$)', args_text):
        shared = True
        # Remove -s flag
        args_text = re.sub(r'(\s|^)-s(\s|$)', ' ', args_text)

    # The rest is the name (trim spaces and quotes)
    name = args_text.strip().strip('"').strip("'")

    # Return the result
    return {
        'name': name,
        'alias': alias,
        'template': template,
        'is_unique': is_unique,
        'shared': shared,
    }

# ----------------------
# Example usage / tests:
if __name__ == '__main__':
    test_cases = [
        'Sally the Sniper',
        'Big Bob -a bob_template -s',
        '"The Razor Ganger" -t razor_template -u',
        'Cyber Samurai -u -a cybsam',
        'Face of the Party -t face_template',
        "Whisper -a whispr",
        "Unnamed"
    ]
    for tc in test_cases:
        print(f"INPUT: {tc}")
        print(parse_npc_create_telegram(tc))
        print('-' * 40)