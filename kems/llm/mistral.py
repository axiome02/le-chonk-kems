from __future__ import annotations

import os

from ._http import post_json
from .client import LLMClient


class MistralClient(LLMClient):
    """Mistral Client (La Plateforme). Key via MISTRAL_API_KEY.
    
    Defaults to mistral-large-4 as required by the 'Le Chonk wants to play' challenge.
    Supports multimodal inputs (text + vision table rendering).
    """

    name = "mistral"
    URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, model: str = "mistral-large-4", api_key: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 2048,
                 pause: float = 1.5, retries: int = 5, timeout: int = 60,
                 reasoning_effort: str | None = "none"):
        self.model = model
        self.api_key = (api_key or os.environ.get("MISTRAL_API_KEY") or "").strip()
        if not self.api_key:
            raise RuntimeError("MISTRAL_API_KEY missing (create a .env, see .env.example).")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.pause = pause
        self.retries = retries
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        super().__init__()

    def chat(self, system: str, user: str, max_tokens: int | None = None,
             image_b64: str | None = None) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        if image_b64:
            image_url = image_b64 if image_b64.startswith("data:") else f"data:image/png;base64,{image_b64}"
            user_content: str | list[dict] = [
                {"type": "text", "text": user},
                {"type": "image_url", "image_url": image_url},
            ]
        else:
            user_content = user

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort

        data = post_json(self.URL, headers, payload, retries=self.retries,
                         timeout=self.timeout, pause=self.pause, name=self.name)
        u = data.get("usage") or {}
        self.calls += 1
        self.prompt_tokens += u.get("prompt_tokens", 0)
        self.completion_tokens += u.get("completion_tokens", 0)
        self.total_tokens += u.get("total_tokens", 0)
        details = u.get("prompt_tokens_details") or {}
        self.cached_tokens += details.get("cached_tokens", 0)
        try:
            choice = data["choices"][0]
            message = choice.get("message") or {}
            content = message.get("content")
            
            reasoning_parts = []
            text_parts = []

            if isinstance(content, list):
                for chunk in content:
                    if isinstance(chunk, str):
                        text_parts.append(chunk)
                    elif isinstance(chunk, dict):
                        c_type = chunk.get("type", "")
                        if c_type == "text":
                            text_parts.append(chunk.get("text", "") or chunk.get("content", ""))
                        elif c_type == "thinking":
                            th_list = chunk.get("thinking") or []
                            if isinstance(th_list, list):
                                for th in th_list:
                                    if isinstance(th, dict):
                                        reasoning_parts.append(th.get("text", ""))
                                    elif isinstance(th, str):
                                        reasoning_parts.append(th)
                            elif isinstance(th_list, str):
                                reasoning_parts.append(th_list)
                        else:
                            text_parts.append(chunk.get("text", "") or chunk.get("content", "") or str(chunk))
                    else:
                        text_parts.append(str(chunk))
                content = "".join(text_parts)
            elif not isinstance(content, str):
                content = str(content) if content is not None else ""

            # Check top-level message reasoning fields
            if message.get("reasoning_content"):
                reasoning_parts.append(str(message.get("reasoning_content")))
            if message.get("thinking") and isinstance(message.get("thinking"), str):
                reasoning_parts.append(message.get("thinking"))

            self.last_reasoning = "\n".join(r for r in reasoning_parts if r).strip()

            # If content text is empty but thinking was captured, use thinking as fallback
            if (not content or not content.strip()) and self.last_reasoning:
                content = self.last_reasoning

            return str(content) if content is not None else ""
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected Mistral response: {data}")
