from __future__ import annotations

import hashlib
from random import Random

from .config import Config
from .engine import rules
from .engine.actions import Call, Take
from .engine.cards import build_deck, is_square
from .engine.signals import NO_SIGNAL, normalize
from .engine.state import Event, GameState, Player
from .engine.views import view_for


# Neutral identifiers: strictly P1..P4
def _name(pid: int) -> str:
    return f"P{pid + 1}"


def _derive(master: int, label: str) -> int:
    h = hashlib.sha256(f"{master}:{label}".encode()).hexdigest()
    return int(h[:16], 16)


def setup(config: Config, models: list[str]) -> GameState:
    rng_cards = Random(config.seed_cards if config.seed_cards is not None
                       else _derive(config.master_seed, "cards"))
    rng_order = Random(config.seed_order if config.seed_order is not None
                       else _derive(config.master_seed, "order"))

    # Teams: P1 (pid 0) & P4 (pid 3) vs P2 (pid 1) & P3 (pid 2)
    players = [
        Player(pid=i, name=_name(i), team=0 if i in (0, 3) else 1, model=models[i])
        for i in range(config.num_players)
    ]

    deck = build_deck(config.num_ranks)
    rng_cards.shuffle(deck)

    hands = {p.pid: [deck.pop() for _ in range(config.hand_size)] for p in players}
    center = [deck.pop() for _ in range(config.center_size)]

    state = GameState(
        config=config,
        players=players,
        hands=hands,
        center=center,
        deck=deck,
        discard=[],
        signals={},
        plans={p.pid: "" for p in players},
        journals={p.pid: [] for p in players},
        team_channels={0: [], 1: []},
        public_log=[],
        rng_cards=rng_cards,
        rng_order=rng_order,
    )
    state.public_log.append(
        Event(0, "SYSTEM", None,
              f"Game start - seed={config.master_seed}, ranks 1..{config.num_ranks}")
    )
    return state


def new_round(state: GameState) -> None:
    """Redistributes everything for the next round. The public chat is never cleared."""
    state.round += 1
    state.turn += 1                 # the new deal already belongs to the first turn of the round
    state.round_turn = 1
    state.centers_played = 0
    state.finished = False
    state.outcome = None

    deck = build_deck(state.config.num_ranks)
    state.rng_cards.shuffle(deck)
    state.hands = {p.pid: [deck.pop() for _ in range(state.config.hand_size)] for p in state.players}
    state.center = [deck.pop() for _ in range(state.config.center_size)]
    state.deck = deck
    state.discard = []
    rules._log(state, "SYSTEM", None,
               f"— Round {state.round} — new deal (score: {state.scores[0]} - {state.scores[1]})")


def _order(state: GameState) -> list[int]:
    order = [p.pid for p in state.players]
    state.rng_order.shuffle(order)
    return order


def _extras_decision(view, agent, action_str: str) -> dict:
    """Extras attached to the timeline step holding a DECISION: the decided action, the hand
    of the decision-maker at that moment, and the raw LLM exchange (prompt, response)."""
    io = getattr(agent, "last_io", None)
    return {
        "action": action_str,
        "hand": [str(c) for c in view.my_hand],
        "square": view.has_square,
        "prompt_user": io[1] if io else None,
        "raw_response": io[2] if io else None,
    }


def _run_team_negotiation(state: GameState, agents: dict, team: int, max_turns: int, is_debrief: bool = False) -> None:
    phase_name = "DEBRIEFING" if is_debrief else "NEGOTIATION"
    players = state.team_players(team)
    if is_debrief:
        burned = rules.signal_burned(state, team)
        state.team_channels[team] = []
        if burned:
            state.team_channels[team].append(
                "[referee] Your secret message was unmasked by the opponents. "
                "It is burned: agree on a new one."
            )
            proposal = ""
            trigger = ""
        else:
            proposal = state.signals.get(team, "")
            trigger = state.triggers.get(team, "")
    else:
        proposal = ""
        trigger = ""

    proposer: int | None = None
    sealed = False

    for nt in range(max_turns):
        pid = players[nt % len(players)]
        view = view_for(state, pid, nego_proposal=proposal,
                        nego_trigger=trigger,
                        nego_remaining=max_turns - nt)
        agent = agents[pid]
        n = agent.debrief(view) if is_debrief else agent.negotiate(view)
        name = state.players[pid].name

        # Detect safety refusals (e.g. LLM guardrail confusing Kem's rules with poker collusion)
        msg_lower = (n.message or "").lower()
        if any(w in msg_lower for w in ("i can't help", "i cannot help", "i won't", "i will not", "collusion", "unfair")):
            n.message = "I am ready to play Kem's with you partner."
            n.proposal = proposal or n.proposal or "banana"
            n.trigger = trigger or n.trigger or "banana"
            n.agree = True

        if n.message:
            state.team_channels[team].append(f"{name}: {n.message}")
        if is_debrief and n.plan:
            state.plans[pid] = n.plan

        agree_word = "YES" if n.agree else "NO"
        plan_extra = f" PLAN='{n.plan}'" if is_debrief and n.plan else ""
        rules.step(state, phase_name, pid,
                   f"{name} is negotiating with their teammate", private=n.message,
                   proposal=n.proposal, trigger=n.trigger, agree=n.agree,
                   **_extras_decision(view, agent,
                                      f"MESSAGE='{n.message}' PROPOSAL='{n.proposal}' "
                                      f"TRIGGER='{n.trigger}' AGREE={agree_word}{plan_extra}"))

        echo = bool(n.proposal and proposal
                    and normalize(n.proposal) == normalize(proposal))
        readback = bool(not n.trigger or (trigger and normalize(n.trigger) == normalize(trigger)))
        if ((n.agree or echo) and proposal and proposer is not None
                and proposer != pid and readback
                and rules.trigger_exploitable(trigger)):
            sealed = True
            break
        if n.proposal:
            proposal, proposer = n.proposal, pid
            trigger = n.trigger or ""

    if not is_debrief:
        state.nego_convergence[team] = sealed
    rules.set_signal(state, team, proposal or NO_SIGNAL, trigger)


def negotiation(state: GameState, agents: dict, teams: tuple[int, ...] | None = None) -> None:
    state.phase = "NEGOTIATION"
    for team in teams if teams is not None else (0, 1):
        _run_team_negotiation(state, agents, team, state.config.max_negotiation_turns, is_debrief=False)


def debriefing_phase(state: GameState, agents: dict) -> None:
    state.phase = "DEBRIEFING"
    for team in (0, 1):
        _run_team_negotiation(state, agents, team, max_turns=4, is_debrief=True)


def exchange_phase(state: GameState, agents: dict) -> None:
    state.phase = "EXCHANGE"
    cfg = state.config
    num_players = cfg.num_players
    consecutive_passes = 0
    st = 0
    order = _order(state)
    while st < cfg.max_subturns_per_center:
        for pid in order:
            name = state.players[pid].name
            if is_square(state.hands[pid]):
                # episode opened in silence: chat is public, a square is private.
                # The player decides whether to keep or break it.
                rules.open_episode(state, pid)
            view = view_for(state, pid)
            action, thought = agents[pid].decide_card(view)
            if thought:
                state.journals.setdefault(pid, []).append(thought)
                rules.step(state, "REFLECTION", pid,
                           f"{name} is evaluating cards",
                           private=thought,
                           **_extras_decision(view, agents[pid], f"THOUGHT: {thought}"))

            if isinstance(action, Take):
                if rules.validate_and_apply_exchange(state, pid, action):
                    rules._log(state, "SWAP", pid,
                               f"{name} takes {action.from_center}, discards {action.discard}",
                               take=str(action.from_center), discard=str(action.discard),
                               **_extras_decision(view, agents[pid],
                                                  f"TAKE {action.from_center} DISCARD {action.discard}"))
                    consecutive_passes = 0
                    if is_square(state.hands[pid]):
                        rules.open_episode(state, pid)
                else:
                    rules._log(state, "SYSTEM", pid, f"{name} attempts an illegal exchange -> passes",
                               **_extras_decision(view, agents[pid],
                                                  f"ILLEGAL {action.from_center}/{action.discard} -> PASS"))
                    consecutive_passes += 1
            else:
                rules._log(state, "PASS", pid, f"{name} passes",
                           **_extras_decision(view, agents[pid], "PASS"))
                consecutive_passes += 1
            
            if consecutive_passes >= num_players:
                break
        if consecutive_passes >= num_players:
            break
        st += 1
    rules.resolve_discard(state)
    rules._log(state, "SWEEP", None,
               f"Center swept -> {' '.join(str(c) for c in state.center)}")


def _recent_text(state: GameState, limit: int = 8) -> str:
    """Public chat window of the current round, for the LLM judge (measurement)."""
    conv = [ev for ev in state.public_log
            if ev.type in ("MESSAGE", "CALL") and ev.round == state.round]
    conv = conv[-limit:]
    return "\n".join(ev.text for ev in conv)


def _judge_kemps_transmission(state: GameState, agents: dict) -> None:
    """Independent LLM judgment (PURE MEASUREMENT, never affects results): did the calling team's
    signal actually circulate, beyond literal word-for-word matching?
    """
    if not state.config.eval_signals:
        return
    o = state.outcome
    if not o or o.get("kind") != "KEMPS":
        return
    team = state.team_of(o["caller"])
    convention = state.signals.get(team, "")
    trigger = state.triggers.get(team, "")
    text = _recent_text(state)
    if text:
        try:
            evaluator = agents.get("evaluator")
            if evaluator is not None and hasattr(evaluator, "judge_signal"):
                o["signal_actually_emitted_llm"] = evaluator.judge_signal(convention, trigger, text)
        except Exception:
            pass


def discussion_phase(state: GameState, agents: dict) -> None:
    state.phase = "DISCUSSION"
    # multiple speech passes per turn: first pass exposes signals, next let partner react in stride
    for _ in range(state.config.discussion_turns):
        order = _order(state)
        calls: dict[int, Call] = {}
        for pid in order:
            view = view_for(state, pid)
            msg, call, plan, thought = agents[pid].decide_discussion(view)
            if thought:
                state.journals.setdefault(pid, []).append(thought)
                rules.step(state, "REFLECTION", pid,
                           f"{state.players[pid].name} is thinking",
                           private=thought,
                           **_extras_decision(view, agents[pid], thought))

            call = call if isinstance(call, Call) else Call("NONE")
            extras = _extras_decision(view, agents[pid],
                                      f"MESSAGE='{msg}' CALL={call.kind} PLAN='{plan}'")
            if plan:
                state.plans[pid] = plan
            if msg and rules.emission_without_square(state, pid, msg):
                # legal: bluff or mistake, not censored. Noted for measurement without writing to public chat.
                state.emissions_without_square.append({
                    "round": state.round, "turn": state.turn, "pid": pid,
                    "model": state.players[pid].model,
                })
            if msg:
                rules._log(state, "MESSAGE", pid,
                           f'{state.players[pid].name}: "{msg}"',
                           **extras)
                if is_square(state.hands[pid]):
                    team = state.team_of(pid)
                    trigger = state.triggers.get(team, "")
                    literal = rules.signal_found(trigger, msg)
                    try:
                        evaluator = agents.get("evaluator")
                        if evaluator is not None and state.config.eval_signals and hasattr(evaluator, "judge_signal"):
                            understood = evaluator.judge_signal(
                                state.signals.get(team, ""), trigger, _recent_text(state))
                        else:
                            understood = None
                    except Exception:
                        understood = None
                    rules.mark_signal_emitted(state, pid, literal, understood)
            else:
                rules.step(state, "DISCUSSION", pid, "", private=None, **extras)
            calls[pid] = call
            if call and call.kind != "NONE":
                rules.resolve_calls(state, {pid: call}, [pid])
                if state.finished:
                    _judge_kemps_transmission(state, agents)
                    return


def play_round(state: GameState, agents: dict) -> None:
    while not state.finished:
        exchange_phase(state, agents)
        if state.finished:
            break
        discussion_phase(state, agents)
        rules.check_end(state)
        if not state.finished:
            state.turn += 1
            state.round_turn += 1


def play_game(config: Config, models: list[str], agents: dict, on_event=None) -> GameState:
    """Plays a MATCH: successive rounds until `points_to_win`."""
    state = setup(config, models)
    for i, p in enumerate(state.players):
        if i in agents:
            client = getattr(agents[i], "client", None)
            if client is not None and hasattr(client, "model"):
                p.model = client.model
    if on_event is not None:
        for ev in state.public_log:
            on_event(ev, state)
        state.on_event = on_event

    negotiation(state, agents)      # happens at turn 0, before any deal
    state.turn = state.round_turn = 1
    while True:
        play_round(state, agents)
        rules.close_round(state)
        if state.match_finished:
            break
        debriefing_phase(state, agents)
        new_round(state)
    return state
