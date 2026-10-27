from __future__ import annotations

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

    def decide_card(self, view: PlayerView):
        raise NotImplementedError

    def reflect(self, view: PlayerView) -> str:
        raise NotImplementedError

    def decide_discussion(self, view: PlayerView) -> tuple[str, Call, str]:
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
            self.last_io = (system, user, raw)
            return raw
        finally:
            _http.api_tracker.current_pid = old_pid

    def _table_b64(self, view: PlayerView) -> str | None:
        if not self.vision:
            return None
        from .engine.render import render_table_base64
        return render_table_base64(view)

    def negotiate(self, view: PlayerView) -> Nego:
        return parse.parse_negotiation(self._ask(prompts.prompt_negotiation(view), pid=view.pid))

    def debrief(self, view: PlayerView) -> Nego:
        return parse.parse_negotiation(self._ask(prompts.prompt_debriefing(view), pid=view.pid))

    def decide_card(self, view: PlayerView):
        b64 = self._table_b64(view)
        prompt = prompts.prompt_micro_card(view)
        return parse.parse_card(self._ask(prompt, pid=view.pid, image_b64=b64), view)

    # Monologue length: 500 tokens for deep tactical deliberation
    MAX_TOKENS_REFLECTION = 500

    def reflect(self, view: PlayerView) -> str:
        """Inner monologue: raw text is kept, no parsing needed."""
        b64 = self._table_b64(view)
        prompt = prompts.prompt_reflection(view)
        return self._ask(prompt, max_tokens=self.MAX_TOKENS_REFLECTION,
                         pid=view.pid, image_b64=b64).strip()

    def decide_discussion(self, view: PlayerView) -> tuple[str, Call, str]:
        b64 = self._table_b64(view)
        # 1) Brain Call: analyze and make the strategic decision
        brain_res = self._ask(prompts.prompt_discussion_brain(view), pid=view.pid, image_b64=b64)
        msg = parse._line(brain_res, "DECISION_MESSAGE") or parse._line(brain_res, "MESSAGE") or ""
        call_str = (parse._line(brain_res, "DECISION_CALL") or parse._line(brain_res, "CALL") or "NONE").strip().upper()
        plan = parse._line(brain_res, "PLAN") or view.my_plan or ""

        # 2) Executor Call: formats the action exactly, isolated from chat and trigger words
        executor_prompt = prompts.prompt_discussion_executor(msg, call_str, plan, view.partner_name)
        executor_res = self._ask(executor_prompt, pid=view.pid)

        parsed_msg, parsed_call, parsed_plan = parse.parse_discussion(executor_res, view)
        final_msg = parsed_msg if parsed_msg else msg
        final_call = parsed_call if parsed_call.kind != "NONE" else Call("KEMPS" if ("KEMPS" in call_str or "KEMS" in call_str) else ("COUNTER" if "COUNTER" in call_str else "NONE"))
        final_plan = parsed_plan or plan

        return final_msg, final_call, final_plan

    def judge_signal(self, convention: str, trigger: str, text: str) -> bool:
        """Measurement judgment (pure measurement, no effect on the game): was the signal
        understood beyond literal matching?"""
        return parse.parse_judgment(
            self._ask(prompts.prompt_judge_signal(convention, trigger, text)))
