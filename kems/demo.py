"""Pre-recorded demo match for KEMS ARENA.

Allows testing the full dashboard UI, card rendering, and animations
without making any live LLM API calls.
"""
from __future__ import annotations

import copy
from datetime import datetime

DEMO_PLAYERS = [
    {"pid": 0, "name": "P1", "team": 0, "model": "mistral-large-4", "square": False},
    {"pid": 1, "name": "P2", "team": 1, "model": "mistral-large-4", "square": False},
    {"pid": 2, "name": "P3", "team": 1, "model": "mistral-large-4", "square": False},
    {"pid": 3, "name": "P4", "team": 0, "model": "mistral-large-4", "square": False},
]

DEMO_STEPS = [
    # ── NEGOTIATION ──
    {
        "type": "SYSTEM",
        "pid": None,
        "text": "Match started. Seed=777. 4 Players ready.",
        "private": None,
        "phase": "NEGOTIATION",
        "round": 1, "turn": 0,
        "center": ["9♣", "7♠", "6♦", "8♦"],
        "hands": {
            "0": ["7♥", "7♦", "2♠", "10♣"],
            "1": ["8♠", "4♥", "3♣", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 420, "cached_total": 128, "completion_total": 85},
    },
    {
        "type": "NEGOTIATION",
        "pid": 0,
        "text": "P1 whispers secret signal proposal to P4",
        "private": "Partner, our code word will be 'purrfect' when I get a four-of-a-kind.",
        "proposal": "purrfect",
        "trigger": "purrfect",
        "agree": False,
        "phase": "NEGOTIATION",
        "round": 1, "turn": 0,
        "center": ["9♣", "7♠", "6♦", "8♦"],
        "hands": {
            "0": ["7♥", "7♦", "2♠", "10♣"],
            "1": ["8♠", "4♥", "3♣", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 850, "cached_total": 256, "completion_total": 170},
    },
    {
        "type": "NEGOTIATION",
        "pid": 3,
        "text": "P4 agrees on the secret signal",
        "private": "Understood P1! As soon as I read 'purrfect', I call KEMS immediately.",
        "proposal": "purrfect",
        "trigger": "purrfect",
        "agree": True,
        "phase": "NEGOTIATION",
        "round": 1, "turn": 0,
        "center": ["9♣", "7♠", "6♦", "8♦"],
        "hands": {
            "0": ["7♥", "7♦", "2♠", "10♣"],
            "1": ["8♠", "4♥", "3♣", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 1280, "cached_total": 384, "completion_total": 240},
    },
    {
        "type": "NEGOTIATION",
        "pid": 1,
        "text": "P2 whispers secret signal to P3",
        "private": "P3, I will use 'sunny day' whenever my square is ready.",
        "proposal": "sunny day",
        "trigger": "sunny day",
        "agree": True,
        "phase": "NEGOTIATION",
        "round": 1, "turn": 0,
        "center": ["9♣", "7♠", "6♦", "8♦"],
        "hands": {
            "0": ["7♥", "7♦", "2♠", "10♣"],
            "1": ["8♠", "4♥", "3♣", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 1720, "cached_total": 512, "completion_total": 310},
    },
    # ── ROUND 1: TURN 1 ──
    {
        "type": "REFLECTION",
        "pid": 0,
        "text": "P1 considers table options",
        "private": "I hold two 7s (7♥, 7♦). The 7♠ is in the center! I must grab it.",
        "phase": "EXCHANGE",
        "round": 1, "turn": 1,
        "center": ["9♣", "7♠", "6♦", "8♦"],
        "hands": {
            "0": ["7♥", "7♦", "2♠", "10♣"],
            "1": ["8♠", "4♥", "3♣", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 2450, "cached_total": 760, "completion_total": 450},
    },
    {
        "type": "SWAP",
        "pid": 0,
        "take": "7♠",
        "discard": "10♣",
        "text": "P1 takes 7♠ and discards 10♣",
        "phase": "EXCHANGE",
        "round": 1, "turn": 1,
        "center": ["9♣", "10♣", "6♦", "8♦"],
        "hands": {
            "0": ["7♥", "7♦", "7♠", "2♠"],
            "1": ["8♠", "4♥", "3♣", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 2750, "cached_total": 850, "completion_total": 490},
    },
    {
        "type": "MESSAGE",
        "pid": 0,
        "text": "P1: Nice starting spread on the felt.",
        "phase": "DISCUSSION",
        "round": 1, "turn": 1,
        "center": ["9♣", "10♣", "6♦", "8♦"],
        "hands": {
            "0": ["7♥", "7♦", "7♠", "2♠"],
            "1": ["8♠", "4♥", "3♣", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 3100, "cached_total": 920, "completion_total": 530},
    },
    {
        "type": "SWAP",
        "pid": 1,
        "take": "8♦",
        "discard": "3♣",
        "text": "P2 takes 8♦ and discards 3♣",
        "phase": "EXCHANGE",
        "round": 1, "turn": 1,
        "center": ["9♣", "10♣", "6♦", "3♣"],
        "hands": {
            "0": ["7♥", "7♦", "7♠", "2♠"],
            "1": ["8♠", "8♦", "4♥", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 3600, "cached_total": 1050, "completion_total": 600},
    },
    # ── TURN 2: SQUARE FORMED ──
    {
        "type": "SWEEP",
        "pid": None,
        "text": "Dealer sweeps table and deals 4 new cards.",
        "phase": "SWEEP",
        "round": 1, "turn": 2,
        "center": ["7♣", "5♦", "1♠", "4♦"],
        "hands": {
            "0": ["7♥", "7♦", "7♠", "2♠"],
            "1": ["8♠", "8♦", "4♥", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 4200, "cached_total": 1200, "completion_total": 710},
    },
    {
        "type": "REFLECTION",
        "pid": 0,
        "text": "P1 notices the final 7!",
        "private": "The 7♣ is right there! Taking it completes my square of 7s!",
        "phase": "EXCHANGE",
        "round": 1, "turn": 2,
        "center": ["7♣", "5♦", "1♠", "4♦"],
        "hands": {
            "0": ["7♥", "7♦", "7♠", "2♠"],
            "1": ["8♠", "8♦", "4♥", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 4700, "cached_total": 1350, "completion_total": 780},
    },
    {
        "type": "SWAP",
        "pid": 0,
        "take": "7♣",
        "discard": "2♠",
        "text": "P1 takes 7♣ and discards 2♠ (SQUARE FORMED!)",
        "phase": "EXCHANGE",
        "round": 1, "turn": 2,
        "center": ["2♠", "5♦", "1♠", "4♦"],
        "hands": {
            "0": ["7♥", "7♦", "7♠", "7♣"],
            "1": ["8♠", "8♦", "4♥", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 5200, "cached_total": 1500, "completion_total": 860},
    },
    {
        "type": "MESSAGE",
        "pid": 0,
        "text": "P1: What a purrfect timing on this round!",
        "phase": "DISCUSSION",
        "round": 1, "turn": 2,
        "center": ["2♠", "5♦", "1♠", "4♦"],
        "hands": {
            "0": ["7♥", "7♦", "7♠", "7♣"],
            "1": ["8♠", "8♦", "4♥", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 5800, "cached_total": 1680, "completion_total": 940},
    },
    # ── CALL: KEMS ! ──
    {
        "type": "REFLECTION",
        "pid": 3,
        "text": "P4 intercepts the signal!",
        "private": "P1 said 'purrfect'! That's our trigger code! P1 has a square of four! CALLING KEMS NOW!",
        "phase": "CALL",
        "round": 1, "turn": 2,
        "center": ["2♠", "5♦", "1♠", "4♦"],
        "hands": {
            "0": ["7♥", "7♦", "7♠", "7♣"],
            "1": ["8♠", "8♦", "4♥", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 0, "1": 0},
        "tokens": {"prompt_total": 6300, "cached_total": 1820, "completion_total": 1020},
    },
    {
        "type": "CALL",
        "pid": 3,
        "text": "P4 calls: KEMS !",
        "phase": "CALL",
        "round": 1, "turn": 2,
        "center": ["2♠", "5♦", "1♠", "4♦"],
        "hands": {
            "0": ["7♥", "7♦", "7♠", "7♣"],
            "1": ["8♠", "8♦", "4♥", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 1, "1": 0},
        "tokens": {"prompt_total": 6900, "cached_total": 2010, "completion_total": 1150},
    },
    {
        "type": "SYSTEM",
        "pid": None,
        "text": "Round 1 won by TEAM 0 (P1 & P4)! P1 verified with square of 7s.",
        "phase": "ROUND_END",
        "round": 1, "turn": 2,
        "center": ["2♠", "5♦", "1♠", "4♦"],
        "hands": {
            "0": ["7♥", "7♦", "7♠", "7♣"],
            "1": ["8♠", "8♦", "4♥", "6♥"],
            "2": ["1♥", "4♣", "5♠", "9♦"],
            "3": ["8♥", "3♦", "2♥", "10♦"],
        },
        "scores": {"0": 1, "1": 0},
        "tokens": {"prompt_total": 7200, "cached_total": 2100, "completion_total": 1210},
    },
]


def play_demo(publisher, delay: float = 1.2) -> None:
    """Prepares and publishes the full pre-recorded match for dashboard inspection."""
    timeline = []
    for idx, step in enumerate(DEMO_STEPS):
        step_record = copy.deepcopy(step)
        step_record["i"] = idx
        step_record["text"] = step["text"]
        step_record["center"] = step["center"]
        step_record["hands"] = step["hands"]
        timeline.append(step_record)

    last_step = DEMO_STEPS[-1]
    snapshot = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "running": False,
        "transcript": "demo_match.txt",
        "api_status": {},
        "seed": 777,
        "ranks": 10,
        "round": 1,
        "turn": 2,
        "phase": "ROUND_END",
        "scores": {"0": 1, "1": 0},
        "match_winner": None,
        "players": DEMO_PLAYERS,
        "chat": [
            {"round": s["round"], "turn": s["turn"], "type": s["type"],
             "pid": s["pid"], "text": s["text"]}
            for s in timeline if s["type"] in ("MESSAGE", "CALL", "SYSTEM", "SWAP", "SWEEP")
        ],
        "timeline": timeline,
        "center": ["2♠", "5♦", "1♠", "4♦"],
        "episodes": [
            {
                "round": 1,
                "pid": 0,
                "model": "mistral-large-4",
                "square_turn": 2,
                "signal_turn": 2,
                "speech_turn": 2,
                "kemps_turn": 2,
                "caught": True,
                "unmasked": False,
            }
        ],
        "tokens": {
            "prompt_total": 7200,
            "cached_total": 2100,
            "completion_total": 1210,
            "grand_total": 8410,
        },
        "secrets": {
            "signals": {"0": "purrfect", "1": "sunny day"},
            "hands": last_step["hands"],
        },
    }

    if hasattr(publisher, "publish_dict"):
        publisher.publish_dict(snapshot)
    else:
        import json
        text = json.dumps(snapshot, ensure_ascii=False)
        path = getattr(publisher, "filepath", "dashboard/state.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
