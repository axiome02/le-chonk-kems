from __future__ import annotations

import argparse
import os
import sys
import threading
import time

from .agents import LLMAgent
from .config import Config
from .dashboard import GameRunner, Publisher, start_server
from .llm import _http
from .llm.env import load_env
from .llm.mistral import MistralClient
from .orchestrator import play_game
from .transcript import render


def usage_summary(agents: dict) -> dict:
    per_model: dict[str, dict] = {}
    for a in agents.values():
        client = getattr(a, "client", None)
        if client is None:
            continue
        d = per_model.setdefault(client.name, {"calls": 0, "prompt": 0, "completion": 0, "cached": 0, "total": 0})
        d["calls"] += getattr(client, "calls", 0)
        d["prompt"] += getattr(client, "prompt_tokens", 0)
        d["completion"] += getattr(client, "completion_tokens", 0)
        d["cached"] += getattr(client, "cached_tokens", 0)
        d["total"] += getattr(client, "total_tokens", 0)
    return {
        "per_model": per_model,
        "grand_total": sum(d["total"] for d in per_model.values()),
        "prompt_total": sum(d["prompt"] for d in per_model.values()),
        "completion_total": sum(d["completion"] for d in per_model.values()),
        "cached_total": sum(d["cached"] for d in per_model.values()),
    }


CLIENTS = {
    "mistral": MistralClient,
}


def build_agent(kind: str, model: str | None = None, pause: float | None = None,
                 temperature: float | None = None, vision: bool = False) -> LLMAgent:
    try:
        classe = CLIENTS[kind]
    except KeyError:
        raise NotImplementedError(
            f"Unknown agent '{kind}'. Available: {', '.join(repr(k) for k in CLIENTS)}."
        )
    kwargs = {}
    if model:
        kwargs["model"] = model
    elif kind == "mistral":
        kwargs["model"] = "mistral-large-4"
    if pause is not None:
        kwargs["pause"] = pause
    if temperature is not None:
        kwargs["temperature"] = float(temperature)
    return LLMAgent(classe(**kwargs), vision=vision)


class EventObserver:
    """Broadcasts each event to observers AND retains state.

    Without it, an exception in `play_game` would lose the `GameState` and the transcript.
    """

    def __init__(self, *observers):
        self.state = None
        self._obs = observers

    def __call__(self, ev, state):
        self.state = state
        _http.api_tracker.state = state
        for o in self._obs:
            o(ev, state)


class LivePrinter:
    """Prints the global chat live in terminal, grouped by turn."""

    def __init__(self, delay: float = 0.0):
        self._turn = None
        self._delay = delay

    def __call__(self, ev, state=None):
        if ev.turn != self._turn:
            self._turn = ev.turn
            header = "Negotiation Setup" if ev.turn == 0 else f"Turn {ev.turn}"
            print(f"\n── {header} ──")
        print(f"   {ev.text}")
        if self._delay:
            time.sleep(self._delay)


def play_match(settings: dict, publisher=None, printer=None) -> dict:
    """Plays a match described by a settings dict. Used by both CLI and dashboard."""
    load_env()
    players = settings.get("players") or [{"agent": "mistral"} for _ in range(4)]
    models = [p.get("model") or p.get("agent", "mistral") for p in players]

    config = Config(
        master_seed=int(settings.get("seed", 42)),
        num_ranks=int(settings.get("ranks", 10)),
        num_players=len(models),
    )
    for key, attr in (
        ("max_turns", "max_turns"),
        ("max_centers", "max_centers_per_round"),
        ("points_to_win", "points_to_win"),
        ("max_rounds", "max_rounds"),
        ("seed_cards", "seed_cards"),
        ("seed_order", "seed_order"),
        ("hand_size", "hand_size"),
        ("center_size", "center_size"),
        ("max_subturns_per_center", "max_subturns_per_center"),
        ("max_negotiation_turns", "max_negotiation_turns"),
        ("discussion_turns", "discussion_turns"),
        ("chat_window", "chat_window"),
    ):
        if settings.get(key) is not None:
            setattr(config, attr, int(settings[key]))
    if settings.get("points") is not None:
        config.points_to_win = int(settings["points"])

    if "eval_signals" in settings:
        config.eval_signals = bool(settings["eval_signals"])

    vision = bool(settings.get("vision", False))
    config.vision = vision

    pause = settings.get("pause")
    agents = {
        i: build_agent(p.get("agent", "mistral"), p.get("model"), pause,
                       p.get("temperature"), vision=vision)
        for i, p in enumerate(players)
    }

    if config.eval_signals:
        eval_agent = settings.get("eval_agent", "mistral")
        eval_model = settings.get("eval_model")
        if eval_agent:
            agents["evaluator"] = build_agent(eval_agent, eval_model, pause, None)
        else:
            config.eval_signals = False
    else:
        config.eval_signals = False
    if publisher is not None:
        publisher.reconnect(lambda: usage_summary(agents))

    _http.api_tracker.publisher = publisher
    _http.api_tracker.state = None
    _http.api_tracker.current_pid = None

    observer = EventObserver(*[o for o in (printer, publisher) if o])
    interrupted = None
    try:
        state = play_game(config, models, agents, on_event=observer)
    except (RuntimeError, KeyboardInterrupt) as e:
        interrupted, state = e, observer.state
        print(f"\n[match interrupted] {e}\n")
        if state is None:
            raise
    usage = usage_summary(agents)
    out = settings.get("out") or os.path.join("transcripts", f"match_{config.master_seed}.txt")
    out_debug = out.replace(".txt", "") + ".debug.txt"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    text = render(state, usage)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    with open(out_debug, "w", encoding="utf-8") as f:
        f.write(render(state, usage, debug=True))

    if publisher is not None:
        publisher.save_transcript(text, os.path.basename(out))
        publisher.write(state, running=False)
    return {"state": state, "usage": usage, "out": out,
            "out_debug": out_debug, "interrupted": interrupted}


def main() -> None:
    ap = argparse.ArgumentParser(description="Kems-Bench — run a match.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--agents", type=str, default="mistral,mistral,mistral,mistral",
                    help="comma-separated list among: " + ", ".join(repr(k) for k in CLIENTS))
    ap.add_argument("--ranks", type=int, default=10)
    ap.add_argument("--points", type=int, default=None,
                    help="round wins needed to win the match")
    ap.add_argument("--max-rounds", type=int, default=None,
                    help="maximum number of rounds (1 = a single round, even if it's a draw).")
    ap.add_argument("--max-turns", type=int, default=None)
    ap.add_argument("--max-centers", type=int, default=None)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--live", action="store_true", help="prints the public chat live in the terminal")
    ap.add_argument("--delay", type=float, default=0.0, help="pause (s) between events in --live mode")
    ap.add_argument("--dashboard", action="store_true",
                    help="publishes live state and serves the local dashboard")
    ap.add_argument("--port", type=int, default=8000, help="dashboard port")
    ap.add_argument("--serve", action="store_true",
                    help="starts only the dashboard: games are launched from the page")
    ap.add_argument("--seed-cards", type=int, default=None, help="shuffle seed (default: derived from --seed)")
    ap.add_argument("--seed-order", type=int, default=None, help="play-order seed (default: derived)")
    ap.add_argument("--model", type=str, default="mistral-large-4",
                    help="model to use, defaults to 'mistral-large-4'.")
    ap.add_argument("--vision", action="store_true",
                    help="enable multimodal vision harness (renders card table frames for Mistral Large 4)")
    ap.add_argument("--pause", type=float, default=None,
                    help="pause (s) between two API calls. Increase on HTTP 429 (e.g. 2)")
    ap.add_argument("--eval", action="store_true", dest="eval", default=False,
                    help="enable optional LLM signal evaluation at round end (default: False)")
    ap.add_argument("--no-eval", action="store_false", dest="eval",
                    help="disable LLM signal evaluation")
    ap.add_argument("--eval-agent", type=str, default="mistral",
                    help="provider for the evaluator (default: mistral)")
    ap.add_argument("--eval-model", type=str, default=None,
                    help="specific model for the evaluator")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    load_env()

    kinds = [k.strip() for k in args.agents.split(",")]

    publisher = None
    if args.dashboard or args.serve:
        publisher = Publisher()
        url = start_server(port=args.port, runner=GameRunner(publisher))
        print(f"Dashboard: {url}")
        if args.serve:
            print("Server mode: launch a game from the page. Ctrl+C to stop.\n")

        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return

    settings = {
        "seed": args.seed, "ranks": args.ranks, "out": args.out, "pause": args.pause,
        "max_turns": args.max_turns, "max_centers": args.max_centers,
        "points_to_win": args.points, "max_rounds": args.max_rounds,
        "seed_cards": args.seed_cards, "seed_order": args.seed_order,
        "vision": args.vision,
        "players": [{"agent": k, "model": args.model} for k in kinds],
        "eval_signals": args.eval,
        "eval_agent": args.eval_agent,
        "eval_model": args.eval_model,
    }
    try:
        res = play_match(settings, publisher,
                         LivePrinter(delay=args.delay) if args.live else None)
    except (RuntimeError, NotImplementedError) as e:
        print(f"[error] {e}")
        sys.exit(1)

    state, usage = res["state"], res["usage"]
    out, out_debug, interrupted = res["out"], res["out_debug"], res["interrupted"]
    w = state.match_winner
    res_str = "draw" if w is None else f"team {w}"
    header = "GAME INTERRUPTED (partial state saved)" if interrupted else f"Match finished -> {res_str}"
    print(f"{header} | score {state.scores[0]}-{state.scores[1]} "
          f"| {len(state.round_history)} rounds | {state.turn} turns")
    print(f"Total tokens: {usage['grand_total']}")
    print(f"Transcript      : {out}")
    print(f"Debug transcript: {out_debug}")
    if interrupted:
        sys.exit(1)


def chonk_main() -> None:
    """1-Click Launcher for Le Chonk Kems with mistral-large-4."""
    from pathlib import Path
    import webbrowser

    print("=" * 65)
    print("🃏 Starting KEMS ARENA — Mistral Large 4 Game Harness 🃏")
    print("=" * 65)

    # Clean previous match state so dashboard starts fresh from 0
    for stale_file in ("dashboard/state.json", "dashboard/state.json.tmp", "dashboard/match.txt", "llm_debug.log"):
        p = Path(stale_file)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    env_path = Path(".env")
    if not env_path.exists():
        print("\n[!] .env file not found!")
        example_path = Path(".env.example")
        if example_path.exists():
            env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
            print("[+] Created .env from .env.example.")
        print("[!] Please set your MISTRAL_API_KEY in .env before launching a live match.\n")

    port = 8000
    dashboard_url = f"http://127.0.0.1:{port}"

    def open_browser():
        time.sleep(1.2)
        print(f"[+] Opening browser at {dashboard_url} ...")
        webbrowser.open(dashboard_url)

    threading.Thread(target=open_browser, daemon=True).start()

    sys.argv = [
        sys.argv[0],
        "--serve",
        "--port", str(port),
        "--model", "mistral-large-4",
    ]
    main()


if __name__ == "__main__":
    main()
