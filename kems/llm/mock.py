from __future__ import annotations

from .client import LLMClient


class MockClient(LLMClient):
    """Simulated offline client for 100% free dry-run testing.
    
    Produces deterministic, valid responses for all phases without any network calls.
    """

    name = "mock"

    def __init__(self, model: str = "mock-bot", **kwargs):
        self.model = model
        super().__init__()

    def chat(self, system: str, user: str, max_tokens: int | None = None,
             image_b64: str | None = None) -> str:
        self.calls += 1
        self.prompt_tokens += 150
        self.completion_tokens += 30
        self.total_tokens += 180

        sys_lower = system.lower()
        usr_lower = user.lower()

        # 1. Negotiation & Debriefing
        if "secret trigger" in sys_lower or "proposal" in sys_lower or "debrief" in sys_lower:
            return (
                "MESSAGE: Sounds great partner! Let's use 'purrfect' as our code.\n"
                "PROPOSAL: purrfect\n"
                "TRIGGER: purrfect\n"
                "AGREE: YES\n"
                "PLAN: Swap cards quickly"
            )

        # 2. Card exchange
        if "exchange turn" in sys_lower or "action:" in sys_lower or "take one card" in sys_lower:
            return "ACTION: PASS"

        # 3. Reflection (Inner monologue)
        if "inner monologue" in sys_lower or "take a moment to think" in sys_lower:
            return "I am evaluating the table cards and keeping an eye on my partner's signals."

        # 4. Brain discussion call
        if "decision_message" in sys_lower or "public discussion" in sys_lower:
            return (
                "ANALYSIS: Game is progressing nicely.\n"
                "DECISION_MESSAGE: Nice cards on the table today.\n"
                "DECISION_CALL: NONE\n"
                "PLAN: Watch for fours"
            )

        # 5. Executor discussion call
        if "signal_received" in sys_lower or "format the player's decision" in sys_lower:
            return (
                "SIGNAL_RECEIVED: NO\n"
                "MESSAGE: Nice cards on the table today.\n"
                "TRIGGER_CHECK: NO\n"
                "CALL: NONE\n"
                "PLAN: Watch for fours"
            )

        # 6. Evaluation / Judge
        if "grading chat messages" in sys_lower or "judge" in sys_lower:
            return "REASONING: No signal spotted.\nSIGNAL: NO"

        return "MESSAGE: Ready.\nCALL: NONE\nPLAN: Wait"
