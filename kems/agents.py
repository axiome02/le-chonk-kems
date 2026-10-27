from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .engine.actions import Call, Nego
from .engine.views import PlayerView
from .llm import _http, parse, prompts
from .llm.client import LLMClient


class Agent:
    """Core interface: the orchestrator only communicates through this. LLM agents implement it."""

    def negotiate(self, view: PlayerView) -> Nego:
        raise NotImplementedError

    def debrief(self, view: PlayerView) -> Nego:
        raise NotImplementedError

    def decide_card(self, view: PlayerView) -> tuple[Any, str]:
        raise NotImplementedError

    def reflect(self, view: PlayerView) -> str:
        raise NotImplementedError

    def decide_discussion(self, view: PlayerView) -> tuple[str, Call, str, str]:
        raise NotImplementedError

    def judge_signal(self, convention: str, trigger: str, text: str) -> bool:
        raise NotImplementedError


class LLMAgent(Agent):
    """Wraps an LLMClient: constructs prompt from view -> chat() -> parse.

    Stores the last exchange (prompt + raw response) in self.last_io for tracing.
    Supports multimodal table vision when `vision=True`.
    """

    def __init__(self, client: LLMClient, vision: bool = False):
        self.client = client
        self.vision = vision
        self.last_io: tuple[str, str, str] | None = None  # (system, user, raw)

    def _ask(self, prompt: tuple[str, str], max_tokens: int | None = None,
             pid: int | None = None, image_b64: str | None = None) -> str:
        """Sends (system, user) to client, logs the exchange, returns raw string."""
        system, user = prompt
        old_pid = getattr(_http.api_tracker, "current_pid", None)
        _http.api_tracker.current_pid = pid
        try:
            raw = self.client.chat(system, user, max_tokens=max_tokens, image_b64=image_b64)
            if isinstance(raw, list):
                parts = []
                for chunk in raw:
                    if isinstance(chunk, str):
                        parts.append(chunk)
                    elif isinstance(chunk, dict):
                        parts.append(chunk.get("text", "") or chunk.get("content", ""))
                    else:
                        parts.append(str(chunk))
                raw = "".join(parts)
            elif not isinstance(raw, str):
                raw = str(raw) if raw is not None else ""
            self.last_io = (system, user, raw)
            self._log_debug(pid, system, user, raw)
            return raw
        finally:
            _http.api_tracker.current_pid = old_pid

    def _log_debug(self, pid: int | None, system: str, user: str, raw: str) -> None:
        p_name = f"P{pid + 1}" if pid is not None else "Agent"
        model_name = getattr(self.client, "model", getattr(self.client, "name", "LLM"))
        reasoning = getattr(self.client, "last_reasoning", None) or ""
        internal_thought = parse._line(raw, "THOUGHT") or parse._line(raw, "REASONING") or ""

        lines = [
            "\n" + "=" * 72,
            f"[DEBUG LLM] APPEL POUR {p_name} ({model_name})",
            "-" * 72,
            "[PROMPT SYSTEM ENVOYE]:",
            system.strip(),
            "-" * 72,
            "[PROMPT USER ENVOYE]:",
            user.strip(),
        ]
        if reasoning.strip():
            lines.extend([
                "-" * 72,
                "[REFLEXION / THINKING TOKENS MISTRAL]:",
                reasoning.strip(),
            ])
        if internal_thought.strip():
            lines.extend([
                "-" * 72,
                "[MONOLOGUE INTERNE DETECTE (THOUGHT)]:",
                internal_thought.strip(),
            ])
        lines.extend([
            "-" * 72,
            "[REPONSE BRUTE DU MODELE (RAW RESPONSE)]:",
            raw.strip(),
            "=" * 72 + "\n",
        ])
        formatted = "\n".join(lines)

        # Affichage direct dans le terminal VS Code
        try:
            print(formatted, flush=True)
        except Exception:
            try:
                sys.stdout.buffer.write((formatted + "\n").encode("utf-8", errors="replace"))
                sys.stdout.buffer.flush()
            except Exception:
                pass

        # Enregistrement synchronisé dans le fichier llm_debug.log consultable dans VS Code
        try:
            log_path = Path.cwd() / "llm_debug.log"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except OSError:
            pass

    def _table_b64(self, view: PlayerView) -> str | None:
        if not self.vision:
            return None
        from .engine.render import render_table_base64
        return render_table_base64(view)

    def negotiate(self, view: PlayerView) -> Nego:
        return parse.parse_negotiation(self._ask(prompts.prompt_negotiation(view), pid=view.pid))

    def debrief(self, view: PlayerView) -> Nego:
        return parse.parse_negotiation(self._ask(prompts.prompt_debriefing(view), pid=view.pid))

    def decide_card(self, view: PlayerView) -> tuple[Any, str]:
        b64 = self._table_b64(view)
        prompt = prompts.prompt_micro_card(view)
        raw = self._ask(prompt, pid=view.pid, image_b64=b64)
        thought = parse._line(raw, "THOUGHT") or parse._line(raw, "REASONING") or ""
        action = parse.parse_card(raw, view)
        return action, thought

    # Monologue length: 500 tokens for deep tactical deliberation
    MAX_TOKENS_REFLECTION = 500

    def reflect(self, view: PlayerView) -> str:
        """Inner monologue: raw text is kept, no parsing needed."""
        b64 = self._table_b64(view)
        prompt = prompts.prompt_reflection(view)
        return self._ask(prompt, max_tokens=self.MAX_TOKENS_REFLECTION,
                         pid=view.pid, image_b64=b64).strip()

    def decide_discussion(self, view: PlayerView) -> tuple[str, Call, str, str]:
        b64 = self._table_b64(view)
        prompt = prompts.prompt_discussion(view)
        raw = self._ask(prompt, pid=view.pid, image_b64=b64)
        thought = parse._line(raw, "THOUGHT") or parse._line(raw, "ANALYSIS") or ""
        msg, call, plan = parse.parse_discussion(raw, view)
        return msg, call, plan, thought

    def judge_signal(self, convention: str, trigger: str, text: str) -> bool:
        """Measurement judgment (pure measurement, no effect on the game): was the signal
        understood beyond literal matching?"""
        return parse.parse_judgment(
            self._ask(prompts.prompt_judge_signal(convention, trigger, text)))
