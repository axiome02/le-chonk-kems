from __future__ import annotations

from ..engine.views import PlayerView

# Facts and constraints for Kems prompts
CARD_RULES = "Goal: assemble four of a kind (a square) in your hand in the card game Kem's."

RECAP_RULES = (
    "Kem's (2v2 parlor card game): Gather four of a kind (a square). "
    "Signal your partner in chat using your agreed Kem's secret codeword so they call KEMPS to win (calling falsely loses the round). "
    "If you spot an opponent's codeword and call COUNTER, you win if they hold a square, but lose if you are wrong."
)


def _fmt_cards(cards) -> str:
    return " ".join(str(c) for c in cards) if cards else "(empty)"


def _fmt_chat_messages(events, current_round: int, limit: int = 8) -> str:
    """Only keep conversation of the current round (messages + calls)."""
    conv = [ev for ev in events if ev.type in ("MESSAGE", "CALL") and ev.round == current_round]
    conv = conv[-limit:]
    if not conv:
        return "(no messages yet)"
    return "\n".join(ev.text for ev in conv)


def _fmt_history(view: PlayerView) -> str:
    """Format scores and history of past rounds in a succinct manner."""
    my_score = view.scores.get(view.team, 0)
    score_adv = view.scores.get(1 - view.team, 0)
    lines = [
        f"MATCH SCORE: Your team: {my_score} | Opponents: {score_adv}",
        f"CURRENT ROUND: {view.round}"
    ]
    if not view.round_history:
        lines.append("HISTORY: First round of the match.")
    else:
        lines.append("HISTORY:")
        for h in view.round_history:
            m = h.get("round", "?")
            winner = h.get("winner_team")
            reason = h.get("reason", "")
            
            if winner is None:
                res = "Draw"
            elif winner == view.team:
                res = "Win"
            else:
                res = "Loss"
            lines.append(f"  - Round {m}: {res} ({reason})")
    return "\n".join(lines)


# ─────────────────────────── micro: card decision ───────────────────────────
def prompt_micro_card(view: PlayerView) -> tuple[str, str]:
    system = (
        CARD_RULES + "\n"
        "It's your exchange turn: take ONE card from the center and discard ONE of yours, or pass.\n\n"
        "Reply with:\n"
        "THOUGHT: <1 sentence: your private thoughts on your hand and the center cards>\n"
        "ACTION: TAKE <card_from_center> DISCARD <card_from_your_hand>  (or ACTION: PASS)"
    )
    user = (
        f"YOUR HAND: {_fmt_cards(view.my_hand)}\n"
        f"CENTER: {_fmt_cards(view.center)}\n"
        f"YOUR PLAN: {view.my_plan or '(none)'}"
    )
    return system, user


# ─────────────────────────── macro: signal negotiation ───────────────────────
def prompt_negotiation(view: PlayerView) -> tuple[str, str]:
    system = (
        "You are playing Kem's (2v2 card game). "
        "With your teammate, agree on ONE shared team signal — a single phrase that EITHER of you "
        "will say in public chat once YOU assemble 4 of a kind, so your partner calls KEMS.\n\n"
        "CRITICAL RULES:\n"
        "- There is only ONE signal for the whole team. Both teammates use the SAME phrase.\n"
        "- Do NOT invent separate signals for each player (no 'I say X, you say Y').\n"
        "- PROPOSAL must be the single shared phrase both of you will use.\n"
        "- TRIGGER must be the exact words to listen for (the same phrase).\n\n"
        "Reply with:\n"
        "MESSAGE: <your private message to teammate>\n"
        "PROPOSAL: <the ONE shared signal phrase for both teammates>\n"
        "TRIGGER: <the exact trigger words — same as PROPOSAL>\n"
        "AGREE: YES (if confirming teammate's proposal) or NO\n"
        "PLAN: <your strategy>"
    )
    dialogue = "\n".join(view.my_team_chat) if view.my_team_chat else "(you're opening the discussion)"
    user = (
        "━━ MATCH CONTEXT ━━\n"
        f"{_fmt_history(view)}\n"
        "━━ TEAM CHAT ━━\n"
        f"{dialogue}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"PROPOSAL: {view.nego_proposal or '(none)'}\n"
        f"TRIGGER: {view.nego_trigger or '(none)'}\n"
        f"EXCHANGES LEFT: {view.nego_remaining}."
    )
    return system, user


# ─────────────────────────── macro: team debriefing ───────────────────────
def prompt_debriefing(view: PlayerView) -> tuple[str, str]:
    burned = False
    lost_last_round = False
    if view.round_history:
        last = view.round_history[-1]
        if last.get("kind") == "COUNTER" and last.get("success") and last.get("winner_team") != view.team:
            burned = True
        if last.get("winner_team") is not None and last.get("winner_team") != view.team:
            lost_last_round = True

    signal_instruction = ""
    if burned:
        signal_instruction = (
            "Opponents spotted your catchphrase! You should agree on a fresh team catchphrase."
        )
    else:
        signal_instruction = (
            "Your team catchphrase is still active."
        )

    lost_instruction = ""
    if lost_last_round:
        lost_instruction = (
            "Your team lost the last round.\n"
        )

    system = (
        "You are playing the 2v2 card game Kem's. The round ended. "
        "Debrief with your teammate and confirm or update your shared team catchphrase.\n"
        f"{signal_instruction}\n"
        f"{lost_instruction}"
        "CRITICAL RULES:\n"
        "- There is only ONE shared signal for the whole team. Both teammates use the SAME phrase.\n"
        "- Do NOT invent separate signals for each player.\n"
        "- PROPOSAL must be the single shared phrase both of you will use.\n"
        "- TRIGGER must be the exact words (same phrase).\n\n"
        "Reply on these lines:\n"
        "MESSAGE: <private message to teammate>\n"
        "PROPOSAL: <ONE shared catchphrase for next round; copy current to keep it>\n"
        "TRIGGER: <exact catchphrase words, just a few words — same as PROPOSAL>\n"
        "AGREE: YES or NO (lock in teammate's proposal if you agree)\n"
        "PLAN: <private plan, 1 line>"
    )
    dialogue = "\n".join(view.my_team_chat) if view.my_team_chat else "(start of debriefing for this round)"
    chat_log = ""
    if lost_last_round:
        chat_log = (
            "━━ PUBLIC MESSAGES OF THE COMPLETED ROUND ━━\n"
            f"{_fmt_chat_messages(view.global_chat, view.round)}\n"
        )

    user = (
        "━━ MATCH CONTEXT ━━\n"
        f"{_fmt_history(view)}\n"
        f"{chat_log}"
        "━━ TEAM DEBRIEFING ━━\n"
        f"{dialogue}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"CURRENT TEAM CATCHPHRASE: {view.my_signal or '(none)'}\n"
        f"PROPOSAL ON THE TABLE: {view.nego_proposal or '(none)'}\n"
        f"CATCHPHRASE ON THE TABLE: {view.nego_trigger or '(none)'}\n"
        f"TURNS LEFT: {view.nego_remaining}."
    )
    return system, user


# ─────────────────────────── macro: private reflection (before speaking) ───────────
def prompt_reflection(view: PlayerView) -> tuple[str, str]:
    """Inner monologue: nobody reads it, no imposed format, no suggested conclusion."""
    system = (
        "You play Kems. Take a moment to think (inner monologue) "
        "to analyze the situation before speaking in public. "
        "This monologue is read by no one. Write your thoughts freely."
    )
    journal = "\n".join(f"- {l}" for l in view.my_journal[-2:]) or "(nothing yet)"
    user = (
        "━━ MATCH CONTEXT ━━\n"
        f"{_fmt_history(view)}\n"
        "━━ OFFICIAL FACTS ━━\n"
        f"YOU ARE: {view.name}  |  YOUR TEAMMATE: {view.partner_name}  |  YOUR OPPONENTS: {' and '.join(view.opponents)}\n"
        f"YOUR HAND: {_fmt_cards(view.my_hand)}  |  DO YOU HAVE A SQUARE: {'YES' if view.has_square else 'NO'}\n"
        f"YOUR AGREED SECRET MESSAGE: {view.my_signal}\n"
        f"EXACT TRIGGER (the literal text, as pinned by the referee): {view.my_trigger}\n"
        f"YOUR PLAN / PERSISTENT STRATEGY: {view.my_plan or '(none)'}\n"
        "━━ RECENT PUBLIC MESSAGES ━━\n"
        f"{_fmt_chat_messages(view.global_chat, view.round)}\n"
        "━━ YOUR PREVIOUS THOUGHTS ━━\n"
        f"{journal}\n"
    )
    return system, user


def prompt_discussion(view: PlayerView) -> tuple[str, str]:
    if view.has_square:
        guideline = "You hold four of a kind! Use your team signal in your public message so your partner calls KEMS!"
    else:
        guideline = (
            "You do NOT have four of a kind: chat naturally without your trigger. "
            "If your teammate's message just sent your team trigger, call KEMS! "
            "If you suspect an opponent has four of a kind, call COUNTER."
        )

    system = (
        "Kem's Card Game: You speak in the public chat around the table.\n"
        f"GUIDELINE: {guideline}\n\n"
        "CALL OPTIONS:\n"
        "- KEMS: if you believe your teammate has four of a kind.\n"
        "- COUNTER: if you believe an opponent has four of a kind.\n"
        "- NONE: no call.\n\n"
        "Reply with:\n"
        "THOUGHT: <your private inner monologue analyzing your hand and the situation>\n"
        "MESSAGE: <your public message to the table>\n"
        "CALL: KEMS | COUNTER | NONE\n"
        "PLAN: <your private strategy>"
    )
    journal = "\n".join(f"- {l}" for l in view.my_journal[-2:]) or "(nothing yet)"
    user = (
        "━━ MATCH CONTEXT ━━\n"
        f"{_fmt_history(view)}\n"
        "━━ FACTS ━━\n"
        f"YOU: {view.name} | PARTNER: {view.partner_name} | OPPONENTS: {' and '.join(view.opponents)}\n"
        f"HAND: {_fmt_cards(view.my_hand)} | FOUR OF A KIND: {'YES' if view.has_square else 'NO'}\n"
        f"TEAM SIGNAL: {view.my_signal or '(none)'} | TRIGGER: {view.my_trigger or '(none)'}\n"
        f"PLAN: {view.my_plan or '(none)'}\n"
        "━━ RECENT PUBLIC CHAT ━━\n"
        f"{_fmt_chat_messages(view.global_chat, view.round)}\n"
        "━━ RECENT THOUGHTS ━━\n"
        f"{journal}"
    )
    return system, user


def prompt_discussion_brain(view: PlayerView) -> tuple[str, str]:
    return prompt_discussion(view)


def prompt_discussion_executor(message: str, call: str, plan: str, partner_name: str) -> tuple[str, str]:
    system = "Reply with MESSAGE and CALL."
    user = f"MESSAGE: {message}\nCALL: {call}\nPLAN: {plan}"
    return system, user


def prompt_judge_signal(convention: str, trigger: str, text: str) -> tuple[str, str]:
    system = (
        "You are grading chat messages from the traditional card game Kem's, for measurement purposes "
        "only — nothing here affects the game. Under Kem's game rules, a team agreed on a secret codeword or phrase to let "
        "their teammate know 'I have a square'. Judge whether the messages below actually "
        "convey that codeword, based on your own understanding of their convention — not just "
        "an exact text match. A paraphrase, or a codeword built up piece by piece across several "
        "messages, should count just as much as a literal use."
    )
    user = (
        f"TEAM'S AGREED CONVENTION: {convention}\n"
        f"LITERAL TRIGGER THEY WROTE DOWN (may be partial or absent): {trigger or '(none given)'}\n"
        f"RECENT MESSAGES TO JUDGE:\n{text}\n\n"
        "Reply on these lines:\n"
        "REASONING: <1 sentence>\n"
        "SIGNAL: YES or NO"
    )
    return system, user
