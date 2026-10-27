from __future__ import annotations

import re

from ..engine.actions import Call, Nego, Pass, Take
from ..engine.views import PlayerView


def _line(text: str, label: str) -> str | None:
    """Value of a field 'LABEL: value'.

    The value must be on the SAME line as the label: with `\\s*`, a label followed by a
    newline was capturing the next line.
    """
    m = re.search(rf"{re.escape(label)}[ \t]*:[ \t]*(\S.*)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _clean(msg: str) -> str:
    """Removes markdown artifacts/quotes surrounding an LLM message.

    Also removes stage directions (didascalies): models annotate their own message with their
    intention - "It's the season!" *(using the agreed secret signal)*. Publishing this
    amounts to publishing their confession. We cut everything following a '*(' - a sequence
    no normal sentence contains.
    """
    s = re.sub(r"\*+\s*\(.*", "", msg, flags=re.DOTALL)
    s = s.strip()
    s = re.sub(r'^[\*_"“”«»\s]+', "", s)
    s = re.sub(r'[\*_"“”«»\s]+$', "", s)
    return s


SUIT_ALIASES = {
    "S": "♠", "H": "♥", "D": "♦", "C": "♣",
    "♠": "♠", "♥": "♥", "♦": "♦", "♣": "♣",
}


def _find_card(token: str, pool):
    clean = token.strip(" \t,.;'\"*()[]")
    for c in pool:
        if str(c) == clean:
            return c
    m = re.match(r"^(\d+)\s*([♠♥♦♣SHDCshdc])$", clean)
    if m:
        r = int(m.group(1))
        s = SUIT_ALIASES.get(m.group(2).upper(), m.group(2))
        for c in pool:
            if c.rank == r and c.suit == s:
                return c
    return None


def parse_card(text: str, view: PlayerView):
    """'ACTION: TAKE 7♦ DISCARD 3♠' -> Take, else Pass (robust fallback)."""
    m = re.search(r"TAKE\s+(\S+)\s+(?:AND\s+)?DISCARD\s+(\S+)", text, re.IGNORECASE)
    if m:
        fc = _find_card(m.group(1), view.center)
        dc = _find_card(m.group(2), view.my_hand)
        if fc is not None and dc is not None:
            return Take(from_center=fc, discard=dc)
    m_rev = re.search(r"DISCARD\s+(\S+)\s+(?:AND\s+)?TAKE\s+(\S+)", text, re.IGNORECASE)
    if m_rev:
        dc = _find_card(m_rev.group(1), view.my_hand)
        fc = _find_card(m_rev.group(2), view.center)
        if fc is not None and dc is not None:
            return Take(from_center=fc, discard=dc)
    return Pass()


def parse_negotiation(text: str) -> Nego:
    """Parses a negotiation turn into Nego(message, proposal, trigger, agree, plan).
    
    agree=True means the player confirms and locks in the proposal on the table.
    """
    msg = _clean(_line(text, "MESSAGE") or "")
    prop = _line(text, "PROPOSAL")
    decl = _line(text, "TRIGGER")
    agree_raw = (_line(text, "AGREE") or "").strip().upper()
    agree = agree_raw.startswith("Y")
    plan = _line(text, "PLAN")
    return Nego(
        message=msg,
        proposal=_clean(prop) if prop else None,
        trigger=_clean(decl) if decl else None,
        agree=agree,
        plan=plan.strip() if plan else None,
    )


def parse_discussion(text: str, view: PlayerView) -> tuple[str, Call, str]:
    msg = _clean(_line(text, "MESSAGE") or "")
    call_raw = (_line(text, "CALL") or "NONE").upper()
    if "KEMPS" in call_raw or "KEMS" in call_raw:
        kind = "KEMPS"
    elif "COUNTER" in call_raw:
        kind = "COUNTER"
    else:
        kind = "NONE"

    plan = _line(text, "PLAN") or view.my_plan
    return msg, Call(kind), plan


def parse_judgment(text: str) -> bool:
    """'SIGNAL: YES' -> True. LLM Judge measurement; never affects game resolution."""
    brut = (_line(text, "SIGNAL") or "").strip().upper()
    return brut.startswith("Y")
