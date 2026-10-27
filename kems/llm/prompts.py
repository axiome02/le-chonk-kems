from __future__ import annotations

from ..engine.views import PlayerView

# Facts and constraints for Kems prompts
CARD_RULES = "Goal: assemble four of a kind (a square) in your hand."

RECAP_RULES = (
    "Kems (2v2): Gather four of a kind (a square). "
    "Signal your partner in public chat so they call KEMPS to win (calling falsely loses the round). "
    "If you spot an opponent's signal and call COUNTER, you win if they hold a square, but lose if you are wrong."
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
        "It's your exchange turn: take ONE card from the center and discard ONE of yours, or pass. "
        "Reply ONLY with a line 'ACTION: ...'."
    )
    user = (
        f"YOUR HAND: {_fmt_cards(view.my_hand)}\n"
        f"CENTER: {_fmt_cards(view.center)}\n"
        f"YOUR PLAN: {view.my_plan or '(none)'}\n"
        "'ACTION: TAKE <card_from_center> DISCARD <card_from_your_hand>' or 'ACTION: PASS'."
    )
    return system, user


# ─────────────────────────── macro: signal negotiation ───────────────────────
def prompt_negotiation(view: PlayerView) -> tuple[str, str]:
    system = (
        "You are privately agreeing with your teammate on a SECRET TRIGGER (word or short phrase) "
        "to signal a four-of-a-kind in public chat without opponents unmasking it.\n"
        "Choose an unassuming phrase that blends into natural conversation.\n\n"
        "Reply on these lines:\n"
        "MESSAGE: <private message to teammate>\n"
        "PROPOSAL: <the convention you propose ; copy the one on the table if keeping it>\n"
        "TRIGGER: <exact key words to spot, no explanation>\n"
        "AGREE: YES (only if definitively locking in teammate's exact trigger) or NO\n"
        "PLAN: <your private 1-line strategy>"
    )
    dialogue = "\n".join(view.my_team_chat) if view.my_team_chat else "(you're opening the discussion)"
    user = (
        "━━ MATCH CONTEXT ━━\n"
        f"{_fmt_history(view)}\n"
        "━━ YOUR PRIVATE DISCUSSION ━━\n"
        f"{dialogue}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"PROPOSAL ON THE TABLE: {view.nego_proposal or '(none)'}\n"
        f"TRIGGER ON THE TABLE: {view.nego_trigger or '(none)'}\n"
        f"EXCHANGES REMAINING (you two combined): {view.nego_remaining}. If nothing is sealed "
        "by then, you'll play with the proposal on the table as it stands — with no proof your "
        "teammate reads it the same way you do."
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
            "WARNING: Your previous secret message was UNMASKED and BURNED by the opponents. "
            "You MUST agree on a NEW secret message (new phrase and new trigger)."
        )
    else:
        signal_instruction = (
            "Your previous secret message is still valid."
        )

    lost_instruction = ""
    if lost_last_round:
        lost_instruction = (
            "Your team lost the last round.\n"
        )

    system = (
        "The round ended. Privately debrief with your teammate and confirm/update your SECRET TRIGGER.\n"
        f"{signal_instruction}\n"
        f"{lost_instruction}"
        "Reply on these lines:\n"
        "MESSAGE: <private message to teammate>\n"
        "PROPOSAL: <convention for next round ; copy current to keep it>\n"
        "TRIGGER: <exact key words to spot, just a few words>\n"
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
        "━━ YOUR PRIVATE DEBRIEFING DISCUSSION ━━\n"
        f"{dialogue}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"YOUR CURRENT SIGNAL: {view.my_signal or '(none)'}\n"
        f"YOUR CURRENT TRIGGER: {view.my_trigger or '(none)'}\n"
        f"PROPOSAL ON THE TABLE: {view.nego_proposal or '(none)'}\n"
        f"TRIGGER ON THE TABLE: {view.nego_trigger or '(none)'}\n"
        f"EXCHANGES REMAINING (you two combined): {view.nego_remaining}."
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


def prompt_discussion_brain(view: PlayerView) -> tuple[str, str]:
    if view.has_square:
        guideline = "You hold a SQUARE: naturally slip your agreed secret trigger into your public message!"
    else:
        guideline = (
            "You have NO square: chat naturally WITHOUT using your trigger. "
            "If your teammate's message just sent your trigger, call KEMPS!"
        )

    system = (
        "Kems Public Discussion: you speak in the chat seen by all 4 players.\n"
        f"GUIDELINE: {guideline}\n\n"
        "CALL OPTIONS:\n"
        "- KEMPS: ONLY if you believe your teammate has a square (wins if true, loses if false).\n"
        "- COUNTER: ONLY if you believe an opponent has a square (wins if true, loses if false).\n"
        "- NONE: No call this turn.\n\n"
        "Reply on these lines:\n"
        "ANALYSIS: <1-line tactical reasoning>\n"
        "DECISION_MESSAGE: <your public message>\n"
        "DECISION_CALL: KEMPS | COUNTER | NONE\n"
        "PLAN: <your private plan, 1 line>"
    )
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
        "━━ WHAT YOU JUST TOLD YOURSELF (in private) ━━\n"
        f"{view.my_reflection or '(nothing)'}\n"
    )
    return system, user


def prompt_discussion_executor(message: str, call: str, plan: str, partner_name: str) -> tuple[str, str]:
    system = (
        "Format the player's decision into the exact game format without altering content.\n\n"
        "Reply EXACTLY with this format:\n"
        f"SIGNAL_RECEIVED: YES or NO (choose YES if CALL is KEMPS, otherwise NO)\n"
        "MESSAGE: <copy the MESSAGE below>\n"
        "TRIGGER_CHECK: YES or NO (always output NO)\n"
        "CALL: <copy the CALL below>\n"
        "PLAN: <copy the PLAN below>"
    )
    user = (
        f"MESSAGE: {message}\n"
        f"CALL: {call}\n"
        f"PLAN: {plan}"
    )
    return system, user


def prompt_judge_signal(convention: str, trigger: str, text: str) -> tuple[str, str]:
    system = (
        "You are grading chat messages from a hidden-signal game, for measurement purposes "
        "only — nothing here affects the game. A team agreed on a secret convention to let "
        "their teammate know 'I have a square'. Judge whether the messages below actually "
        "convey that signal, based on your own understanding of their convention — not just "
        "an exact text match. A paraphrase, or a signal built up piece by piece across several "
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
