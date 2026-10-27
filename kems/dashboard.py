"""Live Dashboard: publishes the game state as JSON, served locally.

The engine remains the sole source of truth; this module projects its state to a
file that the dashboard web page inspects.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import threading
import time
from datetime import datetime

from .engine.cards import is_square
from .engine.state import GameState

_DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard")
DASHBOARD_DIR = _DEFAULT_DIR if os.path.isdir(_DEFAULT_DIR) else "dashboard"
STATE_FILE = "state.json"
TRANSCRIPT_FILE = "match.txt"


def _snapshot(state: GameState, tokens: dict | None, running: bool,
              transcript: str | None = None) -> dict:
    """Projects state to a serializable dict in standard English."""
    players_data = [
        {
            "pid": p.pid,
            "name": p.name,
            "team": p.team,
            "model": p.model,
            "square": is_square(state.hands.get(p.pid, [])),
        }
        for p in state.players
    ]

    chat_data = [
        {
            "round": ev.round,
            "turn": ev.turn,
            "type": ev.type,
            "pid": ev.pid,
            "text": ev.text,
        }
        for ev in state.public_log
    ]

    timeline_data = [
        {
            "i": item["i"],
            "round": item["round"],
            "turn": item["turn"],
            "phase": item["phase"],
            "type": item["type"],
            "pid": item["pid"],
            "text": item.get("text", ""),
            "private": item.get("private"),
            "center": item.get("center"),
            "hands": item.get("hands"),
            **{k: v for k, v in item.items() if k not in (
                "i", "round", "turn", "phase", "type", "pid", "text",
                "private", "center", "hands",
                "prompt_user", "raw_response"
            )}
        }
        for item in state.timeline
    ]

    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "running": running,
        "transcript": transcript,
        "api_status": getattr(state, "api_status", {}),
        "seed": state.config.master_seed,
        "ranks": state.config.num_ranks,
        "round": state.round,
        "turn": state.turn,
        "phase": state.phase,
        "scores": {str(e): n for e, n in state.scores.items()},
        "match_winner": state.match_winner,
        "players": players_data,
        "chat": chat_data,
        "timeline": timeline_data,
        "center": [str(c) for c in state.center],
        "episodes": [
            {
                "round": e.get("round"),
                "pid": e.get("pid"),
                "model": e.get("model"),
                "square_turn": e.get("square_turn"),
                "signal_turn": e.get("signal_turn"),
                "speech_turn": e.get("speech_turn"),
                "llm_signal_turn": e.get("llm_signal_turn"),
                "kemps_turn": e.get("kemps_turn"),
                "caught": e.get("caught"),
                "unmasked": e.get("unmasked"),
            }
            for e in state.episodes
        ],
        "calls_without_signal": state.calls_without_signal,
        "emissions_without_square": state.emissions_without_square,
        "round_history": state.round_history,
        "tokens": tokens or {"grand_total": 0, "per_model": {}},
        "secrets": {
            "signals": {str(e): s for e, s in state.signals.items()},
            "triggers": {str(e): d for e, d in state.triggers.items()},
            "hands": {str(p.pid): [str(c) for c in state.hands.get(p.pid, [])]
                      for p in state.players},
            "journals": {str(pid): list(j) for pid, j in state.journals.items()},
            "team_channels": {str(e): list(c) for e, c in state.team_channels.items()},
        },
    }


class Publisher:
    """Writes the match snapshot for the dashboard."""

    MIN_INTERVAL = 0.5

    def __init__(self, directory: str = DASHBOARD_DIR, tokens=None):
        self.filepath = os.path.join(directory, STATE_FILE)
        self._tokens = tokens or (lambda: None)
        self._last_write = 0.0
        self.transcript = None
        os.makedirs(directory, exist_ok=True)

    def reconnect(self, tokens) -> None:
        """Points to a new match's token summary callback."""
        self._tokens = tokens
        self._last_write = 0.0
        self.transcript = None

    def save_transcript(self, text: str, filename: str) -> None:
        """Saves transcript file next to the dashboard for download."""
        path = os.path.join(os.path.dirname(self.filepath), TRANSCRIPT_FILE)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.transcript = filename

    def __call__(self, ev, state: GameState) -> None:
        now = time.monotonic()
        if now - self._last_write < self.MIN_INTERVAL:
            return
        self._last_write = now
        self.write(state, running=True)

    def publish_dict(self, snapshot: dict) -> None:
        """Writes an already serialized snapshot dict directly to state.json."""
        text = json.dumps(snapshot, ensure_ascii=False)
        tmp = self.filepath + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            for attempt in range(5):
                try:
                    os.replace(tmp, self.filepath)
                    return
                except PermissionError:
                    time.sleep(0.05 * (attempt + 1))
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write(text)
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass

    def write(self, state: GameState, running: bool = True) -> None:
        text = json.dumps(_snapshot(state, self._tokens(), running, self.transcript),
                          ensure_ascii=False)
        tmp = self.filepath + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            for attempt in range(5):
                try:
                    os.replace(tmp, self.filepath)
                    return
                except PermissionError:
                    time.sleep(0.05 * (attempt + 1))
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write(text)
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


class GameRunner:
    """Manages match execution in a background thread."""

    def __init__(self, publisher: Publisher):
        self.publisher = publisher
        self.thread: threading.Thread | None = None
        self.error: str | None = None

    @property
    def busy(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def launch(self, settings: dict) -> None:
        if self.busy:
            raise RuntimeError("a match is already running")
        self.error = None
        self.thread = threading.Thread(target=self._run, args=(settings,), daemon=True)
        self.thread.start()

    def _run(self, settings: dict) -> None:
        from .run import play_match
        try:
            res = play_match(settings, self.publisher)
            if res.get("interrupted"):
                self.error = f"Match Interrupted: {res['interrupted']}"
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"


class _DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Static files server with JSON endpoints for dashboard actions."""

    runner: GameRunner | None = None

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        r = self.runner
        if self.path.startswith("/api/status"):
            return self._json(200, {
                "busy": bool(r and r.busy),
                "error": r.error if r else None,
            })
        if self.path.startswith("/api/config"):
            keys = {
                "mistral": bool(os.environ.get("MISTRAL_API_KEY")),
            }
            return self._json(200, {"keys": keys})
        return super().do_GET()

    def do_POST(self):
        if not self.path.startswith("/api/launch"):
            return self._json(404, {"error": "unknown route"})
        r = self.runner
        if r is None:
            return self._json(503, {"error": "runner unavailable"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            settings = json.loads(self.rfile.read(n) or b"{}")
            r.launch(settings)
            return self._json(200, {"ok": True})
        except Exception as e:
            return self._json(400, {"error": str(e)})


def start_server(directory: str = DASHBOARD_DIR, port: int = 8000,
                 runner: GameRunner | None = None) -> str:
    """Serves the dashboard in the background and returns its local URL."""
    os.makedirs(directory, exist_ok=True)
    handler = functools.partial(_DashboardHandler, directory=directory)
    _DashboardHandler.runner = runner
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}/"
