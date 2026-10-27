from kems.config import Config
from kems.engine.actions import Take
from kems.engine.views import view_for
from kems.llm import parse, prompts
from kems.llm.parse import parse_negotiation
from kems.orchestrator import setup


def test_parse_valid_card():
    cfg = Config(master_seed=1)
    state = setup(cfg, ["mistral"] * 4)
    view = view_for(state, 0)
    fc = view.center[0]
    dc = view.my_hand[0]
    action = parse.parse_card(f"ACTION: TAKE {fc} DISCARD {dc}", view)
    assert isinstance(action, Take)
    assert action.from_center == fc and action.discard == dc


def test_parse_unreadable_card_fallback_pass():
    cfg = Config(master_seed=1)
    state = setup(cfg, ["mistral"] * 4)
    view = view_for(state, 0)
    action = parse.parse_card("blabla incomprehensible", view)
    assert not isinstance(action, Take)  # fallback = Pass


def test_parse_discussion_kemps():
    cfg = Config(master_seed=1)
    state = setup(cfg, ["mistral"] * 4)
    view = view_for(state, 0)
    msg, call, plan = parse.parse_discussion("MESSAGE: hop\nCALL: KEMPS\nPLAN: x", view)
    assert call.kind == "KEMPS"
    assert msg == "hop"

    # Also test KEMS spelling (without P)
    msg2, call2, _ = parse.parse_discussion("MESSAGE: got it\nCALL: KEMS\nPLAN: y", view)
    assert call2.kind == "KEMPS"

    # Test COUNTER
    _, call3, _ = parse.parse_discussion("MESSAGE: caught!\nCALL: COUNTER\nPLAN: z", view)
    assert call3.kind == "COUNTER"


def test_parse_card_variations():
    cfg = Config(master_seed=1)
    state = setup(cfg, ["mistral"] * 4)
    view = view_for(state, 0)
    fc = view.center[0]
    dc = view.my_hand[0]

    # With punctuation
    a1 = parse.parse_card(f"ACTION: TAKE {fc}, DISCARD {dc}.", view)
    assert isinstance(a1, Take)
    assert a1.from_center == fc and a1.discard == dc

    # With 'AND'
    a2 = parse.parse_card(f"ACTION: TAKE {fc} AND DISCARD {dc}", view)
    assert isinstance(a2, Take)

    # Reversed order
    a3 = parse.parse_card(f"ACTION: DISCARD {dc} TAKE {fc}", view)
    assert isinstance(a3, Take)
    assert a3.from_center == fc and a3.discard == dc

    # ASCII letter suits if applicable
    suit_letter = {"♠": "S", "♥": "H", "♦": "D", "♣": "C"}[fc.suit]
    dc_suit_letter = {"♠": "S", "♥": "H", "♦": "D", "♣": "C"}[dc.suit]
    a4 = parse.parse_card(f"ACTION: TAKE {fc.rank}{suit_letter} DISCARD {dc.rank}{dc_suit_letter}", view)
    assert isinstance(a4, Take)
    assert a4.from_center == fc and a4.discard == dc


def test_prompt_does_not_leak_opponent_info():
    """A player's prompt must not contain opponent signal/plan."""
    cfg = Config(master_seed=1)
    state = setup(cfg, ["mistral"] * 4)
    from kems.engine import rules
    rules.set_signal(state, 0, "banana")
    rules.set_signal(state, 1, "SECRET_MOUNTAIN")
    state.plans[1] = "SECRET_PLAN_1"
    view = view_for(state, 0)
    _sys, user = prompts.prompt_discussion_brain(view)
    assert "SECRET_MOUNTAIN" not in user
    assert "SECRET_PLAN_1" not in user


def test_empty_line_does_not_capture_next_line():
    n = parse_negotiation("MESSAGE: ok\nPROPOSAL:\n- Conventions:\nAGREE: NO")
    assert n.proposal is None


def test_trigger_on_same_line():
    n = parse_negotiation("PROPOSAL: sleeping cat\nTRIGGER: the cat is sleeping\nAGREE: YES")
    assert n.trigger == "the cat is sleeping"


def test_didascalie_removed_from_public_message():
    brut = ("MESSAGE: « It's the season! 🌸 » *(clearly, with emphasis and "
            "using the agreed secret signal) »\nCALL: NONE")
    n = parse_negotiation(brut)
    assert n.message == "It's the season! 🌸"


def test_didascalie_with_multiple_asterisks():
    n = parse_negotiation("MESSAGE: Harvest is bountiful 🌾 »** *(signal repetition)")
    assert n.message == "Harvest is bountiful 🌾"


def test_normal_parenthesis_preserved():
    n = parse_negotiation("MESSAGE: nice game (if you will) !")
    assert n.message == "nice game (if you will) !"
