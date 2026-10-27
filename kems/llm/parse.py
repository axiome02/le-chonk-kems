from __future__ import annotations

import re

from ..engine.actions import Call, Nego, Pass, Take
from ..engine.views import PlayerView


def _ensure_str(val) -> str:
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        parts = []
        for x in val:
            if isinstance(x, str):
                parts.append(x)
            elif isinstance(x, dict):
                parts.append(x.get("text", "") or x.get("content", "") or str(x))
            else:
                parts.append(str(x))
        return "\n".join(parts)
    return str(val) if val is not None else ""


def _line(text: str, label: str) -> str | None:
    """Value of a field 'LABEL: value'.

    The value must be on the SAME line as the label: with `[ \t]*`, a label followed by a
    newline was capturing the next line.
    Supports markdown formatting: **LABEL**: value, **LABEL:** value, - **LABEL:** value, etc.
    """
    text = _ensure_str(text)
    clean = re.sub(r"<(?:think|thought)>.*?</(?:think|thought)>", "", text, flags=re.DOTALL)

    pat = rf"(?:^|\n)[ \t]*(?:[-*#>]+\s*)?(?:\*+|_)?{re.escape(label)}(?:\*+|_)?(?:[ \t]*\*)?[ \t]*:[ \t]*(\S.*)"
    m = re.search(pat, clean, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        val = re.sub(r'[\*_"“”«»\s]+$', "", val)
        return val

    return None


def _clean(msg: str) -> str:
    """Removes markdown artifacts/quotes surrounding an LLM message.

    Also removes stage directions (didascalies): models annotate their own message with their
    intention - "It's the season!" *(using the agreed secret signal)*. Publishing this
    amounts to publishing their confession. We cut everything following a '*(' - a sequence
    no normal sentence contains.
    """
    msg = _ensure_str(msg)
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
    text = _ensure_str(text)
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
    clean_text = re.sub(r"<(?:think|thought)>.*?</(?:think|thought)>", "", _ensure_str(text), flags=re.DOTALL).strip()
    msg = _clean(_line(clean_text, "MESSAGE") or "")
    prop = _line(clean_text, "PROPOSAL")
    decl = _line(clean_text, "TRIGGER")
    agree_raw = (_line(clean_text, "AGREE") or "").strip().upper()
    agree = agree_raw.startswith("Y")
    plan = _line(clean_text, "PLAN")

    # Reject placeholder literals that models emit when they have no real proposal yet.
    # Check BEFORE splitting so "N/A" is caught whole rather than producing "N".
    _PLACEHOLDERS = {"none", "n/a", "na", "tbd", "empty", ""}

    # Strip composite triggers like "X (mine) / Y (yours)" — keep only the first segment.
    # This defends against models that invent asymmetric per-player signals despite the prompt.
    if decl:
        if decl.strip().lower().strip("()[]") in _PLACEHOLDERS:
            decl = None
        else:
            first_seg = re.split(r"\s*[/|(]", decl)[0].strip()
            if first_seg:
                decl = first_seg
            # After split, re-check for placeholder fragments like bare "N" from "N/A"
            if decl and len(decl) <= 2:
                decl = None

    # Same sanitization for PROPOSAL
    if prop:
        if prop.strip().lower().strip("()[]") in _PLACEHOLDERS:
            prop = None
        else:
            first_seg = re.split(r"\s*[/|(]", prop)[0].strip()
            if first_seg:
                prop = first_seg
            if prop and len(prop) <= 2:
                prop = None

    # If the model didn't use the exact 'MESSAGE:' prefix, don't leave the message empty!
    if not msg and clean_text:
        for line in clean_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            upper = line_str.upper()
            if any(upper.startswith(k) for k in (
                "PROPOSAL:", "**PROPOSAL", "TRIGGER:", "**TRIGGER", "AGREE:", "**AGREE", "PLAN:", "**PLAN",
                "THOUGHT:", "**THOUGHT", "REASONING:", "**REASONING"
            )):
                continue
            candidate = _clean(line_str)
            if candidate:
                msg = candidate
                break

    return Nego(
        message=msg,
        proposal=_clean(prop) if prop else None,
        trigger=_clean(decl) if decl else None,
        agree=agree,
        plan=plan.strip() if plan else None,
    )


def parse_discussion(text: str, view: PlayerView) -> tuple[str, Call, str]:
    clean_text = re.sub(r"<(?:think|thought)>.*?</(?:think|thought)>", "", _ensure_str(text), flags=re.DOTALL).strip()
    msg = _clean(_line(clean_text, "MESSAGE") or "")
    call_raw = (_line(clean_text, "CALL") or "NONE").upper()
    if "KEMPS" in call_raw or "KEMS" in call_raw:
        kind = "KEMPS"
    elif "COUNTER" in call_raw:
        kind = "COUNTER"
    else:
        kind = "NONE"

    plan = _line(clean_text, "PLAN") or view.my_plan

    if not msg and clean_text:
        for line in clean_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            upper = line_str.upper()
            if any(upper.startswith(k) for k in (
                "CALL:", "**CALL", "PLAN:", "**PLAN",
                "THOUGHT:", "**THOUGHT", "REASONING:", "**REASONING", "ANALYSIS:", "**ANALYSIS"
            )):
                continue
            candidate = _clean(line_str)
            if candidate:
                msg = candidate
                break

    return msg, Call(kind), plan


def parse_judgment(text: str) -> bool:
    """'SIGNAL: YES' -> True. LLM Judge measurement; never affects game resolution."""
    brut = (_line(text, "SIGNAL") or "").strip().upper()
    return brut.startswith("Y")
