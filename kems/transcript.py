from __future__ import annotations

from .engine.cards import is_square, square_rank
from .engine.state import GameState


def _indent(text: str, prefix: str = "        | ", empty: str = "(empty)") -> str:
    if not text:
        return prefix + empty
    return "\n".join(prefix + line for line in text.splitlines())


def render(state: GameState, usage: dict | None = None, debug: bool = False) -> str:
    """Generates the game transcript. If debug=True, includes granular LLM prompts & decisions."""
    L: list[str] = []
    
    if debug:
        L.append("#" * 72)
        L.append("DETAILED INSPECTION TRACE (LLM PROMPTS & DECISIONS)")
        L.append(f"Game seed={state.config.master_seed}, ranks 1..{state.config.num_ranks}")
        for p in state.players:
            L.append(f"  Player {p.pid}: {p.name} (Team {p.team}) [{p.model}]")
        L.append("#" * 72)

        # Private team chats
        L.append("\n=== PRIVATE TEAM DISCUSSIONS (NEGOTIATION) ===")
        for team in (0, 1):
            L.append(f"\n--- Team {team} (Signal: '{state.signals.get(team, '')}') ---")
            for line in state.team_channels.get(team, []):
                L.append(f"   {line}")

        # Decisions
        L.append("\n=== DETAILED TIMELINE ===")
        current_turn = None
        current_phase = None
        for e in state.timeline:
            if "action" not in e:
                continue
            if e["turn"] != current_turn:
                current_turn = e["turn"]
                current_phase = None
                header = "Setup & Negotiation" if e["turn"] == 0 else f"Round {e.get('round', 1)} — Turn {e['turn']}"
                L.append(f"\n{'─' * 60}\n=== {header} ===")

            phase = {"SWAP": "EXCHANGE", "PASS": "EXCHANGE", "SYSTEM": "EXCHANGE",
                     "MESSAGE": "DISCUSSION"}.get(e["type"], e["type"])
            if phase != current_phase:
                current_phase = phase
                L.append(f"\n--- Phase: {current_phase} ---")

            player = state.players[e["pid"]]
            square = " [SQUARE!]" if e.get("square") else ""
            L.append(f"\n  > {player.name} (Team {player.team}){square}")
            hand_cards = e.get("hand", [])
            L.append(f"      Hand:   {' '.join(hand_cards)}")
            L.append(f"      Center: {' '.join(e['center'])}")
            L.append(f"      Action: {e['action']}")
            if e.get("prompt_user") is not None:
                L.append("      Prompt sent:")
                L.append(_indent(e["prompt_user"]))
                raw_resp = e.get("raw_response", "")
                L.append("      Raw LLM response:")
                L.append(_indent(raw_resp or ""))

    # Standard clean story log
    L.append("=" * 64)
    L.append("KEMS ARENA — MATCH TRANSCRIPT")
    L.append(f"Seed: {state.config.master_seed} | Ranks: 1..{state.config.num_ranks} | Points to win: {state.config.points_to_win}")
    L.append("PLAYERS:")
    for p in state.players:
        L.append(f"  - {p.name} (Team {p.team}) — {p.model}")
    L.append("=" * 64)

    # Global chat log
    current_turn = None
    current_round = None
    for ev in state.public_log:
        if ev.round != current_round:
            current_round = ev.round
            current_turn = None
            L.append(f"\n{'━' * 64}\nRound {ev.round}\n{'━' * 64}")
        if ev.turn != current_turn:
            current_turn = ev.turn
            header = "Negotiation Setup" if ev.turn == 0 else f"Turn {ev.turn}"
            L.append(f"\n── {header} ──")
        L.append(f"   {ev.text}")

    # End revelations
    L.append("\n" + "=" * 64)
    L.append("REVELATIONS & EVALUATION")
    for team in (0, 1):
        L.append(f"\n  Team {team} secret negotiation:")
        for line in state.team_channels.get(team, []):
            L.append(f"      {line}")
        L.append(f"  Final signal (Team {team}): '{state.signals.get(team, '')}'")

    for p in state.players:
        h = state.hands[p.pid]
        square_str = f" [SQUARE OF {square_rank(h)}s]" if is_square(h) else ""
        L.append(f"  Final hand of {p.name}: {' '.join(str(c) for c in h)}{square_str}")

    L.append("\n  Inner Monologues (Chain-of-Thought):")
    for p in state.players:
        entries = state.journals.get(p.pid, [])
        if not entries:
            continue
        L.append(f"\n    {p.name} (Team {p.team}):")
        for i, entry in enumerate(entries, 1):
            L.append(f"      [{i}] " + "\n          ".join(entry.splitlines()))

    L.append("\n  Square & Signal Episodes:")
    if not state.episodes:
        L.append("    (no square was formed this match)")
    for e in state.episodes:
        name = state.players[e["pid"]].name
        if e.get("signal_turn"):
            emitted = f"trigger sent turn {e['signal_turn']}"
        elif e.get("speech_turn"):
            emitted = f"spoke turn {e['speech_turn']} (not recognized)"
        else:
            emitted = "never spoke"
        caught = f"caught turn {e['kemps_turn']}" if e.get("caught") else "not caught"
        unmasked_str = "" if e.get("unmasked") is None else (" [unmasked by opponents]" if e["unmasked"] else " [signal stayed secret]")
        L.append(f"    Round {e['round']} | {name} ({e['model']}) : square turn {e['square_turn']} -> {emitted} -> {caught}{unmasked_str}")

    if state.calls_without_signal:
        L.append("\n  Calls made without signal detection:")
        for a in state.calls_without_signal:
            issue = "WIN" if a["winner"] else "LOSS"
            L.append(f"    Round {a['round']} turn {a['turn']} : {state.players[a['pid']].name} ({a['model']}) -> {issue}")

    if state.emissions_without_square:
        L.append("\n  Signal emitted without a square:")
        for em in state.emissions_without_square:
            L.append(f"    Round {em['round']} turn {em['turn']} : {state.players[em['pid']].name} ({em['model']})")

    L.append("\n  Match Progress:")
    for o in state.round_history:
        w = o.get("winner_team")
        winner_name = "Draw" if w is None else f"Team {w}"
        L.append(f"    Round {o.get('round', '?')} : {winner_name} ({o.get('reason', '?')})")

    L.append("-" * 64)
    L.append(f"  Final score: Team 0: {state.scores[0]} | Team 1: {state.scores[1]}")
    if state.match_winner is None:
        L.append("  Match ended in a DRAW")
    else:
        L.append(f"  Match winner: Team {state.match_winner}")
    L.append(f"  Summary: {len(state.round_history)} rounds played, {state.turn} turns total")

    if usage is not None:
        per = " | ".join(f"{n}: {d['total']} tok ({d['calls']} calls)"
                          for n, d in usage.get("per_model", {}).items())
        L.append(f"  Total tokens: {usage.get('grand_total', 0)}" + (f"  [{per}]" if per else ""))
    L.append("=" * 64)
    return "\n".join(L)
