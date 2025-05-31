"""
core/diceroller.py

Core dice-rolling logic for the ShadowDaemon bot.
Provides argument parsing for the `/r` command, threshold keyword mapping,
wave-based (Rule of Six) dice pool rolling, and computation of roll results
including hits, net hits, outcome, and glitch detection.
"""
import random
from typing import Dict, Any, List, Optional, Tuple

RollArgs = Tuple[int, bool, Optional[int], Optional[int], str]
# (dice_pool, edge, limit, threshold, comment)

def parse_threshold(keyword: str, edition: str = "SR5") -> Optional[int]:
    """
    Map a difficulty keyword to its numeric threshold based on the Shadowrun edition.

    Args:
        keyword: Difficulty keyword (e.g. "easy", "hard", "ex", etc.).
        edition: Edition code, "SR4" or "SR5". Keywords differ by edition.

    Returns:
        The numeric threshold corresponding to the keyword, or None if not recognized
        or unsupported for the given edition.
    """
    key = keyword.lower().replace(" ", "")
    if edition == "SR4":
        thresholdmap = {
            "easy": 1, "ea": 1,
            "average": 2, "av": 2,
            "hard": 4, "ha": 4,
            "extreme": 6, "ex": 6,
        }
    elif edition == "SR5":
        thresholdmap = {
            "easy": 1, "ea": 1,
            "average": 2, "av": 2,
            "hard": 4, "ha": 4,
            "veryhard": 6, "vh": 6,
            "extreme": 8, "ex": 8,
        }
    else:
        return None

    return thresholdmap.get(key)

def parse_roll_args(
    raw_args: list[str], 
    edition: str
) -> RollArgs:
    """
    Parse raw `/r` command tokens into structured roll parameters.

    Args:
        raw_args: List of command arguments, e.g. ["10e", "5", "hard", "Sneak move"].
        edition: Edition code ("SR4", "SR5", "SR6").

    Returns:
        A tuple (dice_pool, edge, limit, threshold, comment):
          - dice_pool: Number of dice to roll.
          - edge: Whether edge-based rerolls (Rule of Six) are enabled.
          - limit: Optional max hits (SR5 only).
          - threshold: Optional target hits for success.
          - comment: Remaining text as user comment.
    """
    args = raw_args[:]
    # 1) Dice & edge flag
    raw = args.pop(0)
    edge = False
    if raw.lower().endswith("e"):
        edge = True
        raw = raw[:-1]
    dice_pool = int(raw)
    # 2) Limit (SR5 only)
    limit = None
    if edition == "SR5" and args and args[0].isdigit():
        limit = int(args.pop(0))
    # 3) Threshold based on edition rules
    threshold = None
    if args:
        token = args[0]
        # SR5: allow 't'-prefixed int
        if edition == "SR5" and token.lower().startswith("t"):
            token = token[1:]
        # If digit accept as threshold
        if token.isdigit():
            threshold = int(token)
        # If alpha parse for SR4 and SR5
        elif edition != "SR6":
            threshold = parse_threshold(token, edition)
        # If valid threshold, move to next arg
        if threshold is not None:
            args.pop(0)
    #  4) Remainder is comment
    comment = " ".join(args).strip()
    return dice_pool, edge, limit, threshold, comment

def roll_dicepool(
    num_dice: int,
    edge: bool = False,
) -> List[List[int]]:
    """
    Roll a pool of dice with optional edge-based rerolls (Rule of Six).

    Args:
        num_dice: Number of six-sided dice to roll initially.
        edge: If True, each 6 rolled is rerolled in subsequent waves.

    Returns:
        A list of "waves", where each wave is a list of integers representing
        the results of that round of rolls. Subsequent waves occur only if
        edge=True and 6s were rolled in the prior wave.
    """
    rolls_by_wave: List[List[int]] = []
    pool = num_dice
    while pool > 0:
        wave = random.choices([1, 2, 3, 4, 5, 6], k=pool)
        rolls_by_wave.append(wave)
        if edge:
            # reroll the 6s
            pool = sum(1 for d in wave if d == 6)
        else:
            pool = 0
    return rolls_by_wave

def get_roll_results(
    num_dice: int,
    edge: bool,
    limit: Optional[int],
    threshold: Optional[int],
    edition: str
) -> Dict[str, Any]:
    """
    Compute structured roll results including hits, net hits, outcome, and glitch.

    Args:
        num_dice: Number of dice to roll.
        edge: Edge-based rerolls flag.
        limit: Optional maximum hits cap (SR5 only).
        threshold: Optional hits required for success.
        edition: Edition code ("SR4", "SR5", "SR6").

    Returns:
        A dictionary with keys:
         - "waves": List of roll waves (List[List[int]]).
         - "hits": Total hit count after applying limit.
         - "net_hits": hits - threshold, or None if threshold not provided.
         - "outcome": One of "Success", "Failure", or "Critical Success".
         - "glitch": "Glitch", "Critical Glitch", or empty string.
    """
    # 1) roll waves
    waves = roll_dicepool(num_dice, edge)
    # 2) flatten for counts
    all_rolls = [d for wave in waves for d in wave]
    raw_hits = sum(1 for d in all_rolls if d >= 5)
    ones = sum(1 for d in all_rolls if d == 1)
    # 3) apply limit (only SR5)
    if edition == "SR5" and limit is not None:
        hits = min(raw_hits, limit)
    else:
        hits = raw_hits
    # 4) initialize net_hits and outcome defaults
    net_hits: Optional[int] = None
    outcome: str = ""
    # 5) calculate net hits & outcome if threshold provided
    if threshold is not None:
        net_hits = hits - threshold
        if net_hits <= 0:
            outcome = "Failure!"
        elif net_hits >= 4 and edition == "SR4":
            outcome = "Critical Success!"
        else:
            outcome = "Success!"
    # 6) determine glitch
    if ones >= len(all_rolls)/2:
        glitch = "Glitch" if hits > 0 else "Critical Glitch"
    else:
        glitch = ""

    return {
        "waves": waves,
        "raw_hits": raw_hits,
        "hits": hits,
        "limit": limit,
        "net_hits": net_hits,
        "outcome": outcome,
        "glitch": glitch,
    }