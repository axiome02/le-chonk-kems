from kems.config import Config
from kems.engine.actions import Nego
from kems.llm.parse import parse_negotiation
from kems.orchestrator import negotiation, setup


class _Stub:
    """Scripted negotiation agent: (msg, proposal, agree) or (msg, proposal, agree, trigger, plan).
    Default trigger: trigger = proposal if not explicitly given."""

    def __init__(self, scripted):
        self._scripted = scripted
        self._i = 0

    def negotiate(self, view):
        item = self._scripted[min(self._i, len(self._scripted) - 1)]
        msg, prop, agree = item[0], item[1], item[2]
        decl = item[3] if len(item) > 3 else prop
        plan = item[4] if len(item) > 4 else None
        self._i += 1
        return Nego(message=msg, proposal=prop, trigger=decl, agree=agree, plan=plan)

    def debrief(self, view):
        return self.negotiate(view)


def test_parse_negotiation_format():
    n = parse_negotiation("MESSAGE: hello\nPROPOSAL: 🌙\nTRIGGER: 🌙\nAGREE: YES")
    assert n.message == "hello" and n.proposal == "🌙" and n.agree is True
    assert n.trigger == "🌙"

    n2 = parse_negotiation("MESSAGE: wait\nPROPOSAL: moon\nAGREE: NO")
    assert n2.proposal == "moon" and n2.agree is False and n2.trigger is None


def _run_nego(scripts, **cfg_kw):
    cfg = Config(master_seed=1, **cfg_kw)
    state = setup(cfg, ["stub"] * 4)          # team 0 = players 0, 3; team 1 = players 1, 2
    agents = {pid: _Stub(scripts[pid]) for pid in range(4)}
    negotiation(state, agents)
    return state


def test_negotiation_seals_on_partner_agreement():
    # agreeing player re-writes trigger of the table (read-back): agreement sealed
    scripts = {
        0: [("I propose MOON", "MOON", False)],
        3: [("sounds good, agreed", None, True, "MOON")],
        1: [("idea: SUN", "SUN", False), ("perfect", None, True, "🌙")],
        2: [("too obvious, rather 🌙", "🌙", False)],
    }
    state = _run_nego(scripts)
    assert state.signals[0] == "MOON"
    assert state.signals[1] == "🌙"           # proposal refined by player 2, validated by 1
    assert state.nego_convergence == {0: True, 1: True}
    assert len(state.team_channels[0]) == 2   # real back-and-forth
    assert len(state.team_channels[1]) == 3


def test_negotiation_no_self_agreement_on_first_turn():
    # player 0 says AGREE: YES at first turn -> ignored (nothing from partner on table yet)
    scripts = {
        0: [("locking in immediately", "SOLO", True)],
        3: [("uh ok", None, True, "SOLO")],
        1: [("x", "X", True)],
        2: [("y", None, True)],
    }
    state = _run_nego(scripts)
    assert state.signals[0] == "SOLO"          # locked at turn 1 by player 3, not turn 0


def test_negotiation_freezes_last_proposal_without_agreement():
    scripts = {
        0: [("a", "A", False)],
        3: [("b", "B", False)],
        1: [("c", "C", False)],
        2: [("d", "D", False)],
    }
    state = _run_nego(scripts, max_negotiation_turns=2)
    assert state.signals[0] == "B"             # last proposal (player 3), lacking agreement
    assert state.signals[1] == "D"
    assert state.nego_convergence == {0: False, 1: False}


def test_recopied_proposal_counts_as_tacit_agreement():
    scripts = {
        0: [("I propose MOON", "MOON", False)],
        3: [("I keep MOON", "MOON", False)],       # copy -> tacit agreement, stops early
        1: [("x", "X", False)], 2: [("x", "X", False)],
    }
    state = _run_nego(scripts)
    assert state.signals[0] == "MOON"
    assert len(state.team_channels[0]) == 2          # 2 turns, not 10


def test_agreement_without_readback_does_not_seal():
    scripts = {
        0: [("I propose MOON", "MOON", False), ("re-MOON", "MOON", False)],
        3: [("ok!", None, True, "SUN")],           # YES but divergent trigger
        1: [("x", "X", False)], 2: [("x", "X", False)],
    }
    state = _run_nego(scripts, max_negotiation_turns=4)
    assert state.nego_convergence[0] is False
    assert len(state.team_channels[0]) == 4        # no seal: all 4 turns played


def test_agreement_on_unusable_trigger_does_not_seal():
    scripts = {
        0: [("let's say 42", "42", False)],
        3: [("ok 42", None, True, "42")],           # read-back correct but meaningless trigger
        1: [("x", "X", False)], 2: [("x", "X", False)],
    }
    state = _run_nego(scripts, max_negotiation_turns=4)
    assert state.nego_convergence[0] is False


def test_echo_without_same_trigger_does_not_seal():
    scripts = {
        0: [("I propose MOON", "MOON", False), ("again", "MOON", False)],
        3: [("I keep MOON", "MOON", False, "STAR")],   # same proposal, different trigger
        1: [("x", "X", False)], 2: [("x", "X", False)],
    }
    state = _run_nego(scripts, max_negotiation_turns=4)
    assert state.nego_convergence[0] is False


def test_repeating_own_proposal_not_enough():
    scripts = {
        0: [("I propose MOON", "MOON", False), ("always MOON", "MOON", False)],
        3: [("hmm", "SUN", False)],
        1: [("x", "X", False)], 2: [("x", "X", False)],
    }
    state = _run_nego(scripts, max_negotiation_turns=4)
    assert len(state.team_channels[0]) == 4


def test_debriefing_phase():
    from kems.orchestrator import debriefing_phase
    scripts = {
        0: [("switching to SUN", "SUN", False, "SUN", "Plan 0")],
        3: [("agreed on SUN", None, True, "SUN", "Plan 3")],
        1: [("keep X", "X", False, "X", "Plan 1")],
        2: [("ok X", "X", False, "X", "Plan 2")],
    }
    cfg = Config(master_seed=1)
    state = setup(cfg, ["stub"] * 4)
    state.signals[0] = "MOON"
    state.triggers[0] = "MOON"
    state.signals[1] = "X"
    state.triggers[1] = "X"

    agents = {pid: _Stub(scripts[pid]) for pid in range(4)}
    debriefing_phase(state, agents)

    # Team 0 should have converged on SUN
    assert state.signals[0] == "SUN"
    assert state.triggers[0] == "SUN"

    # Team 1 kept X
    assert state.signals[1] == "X"
    assert state.triggers[1] == "X"

    # Plans should be updated
    assert state.plans[0] == "Plan 0"
    assert state.plans[3] == "Plan 3"
