from __future__ import annotations

import random
import threading
import time

import requests

MAX_WAIT = 60.0  # seconds: beyond this, it's an exhausted quota, not a rate limit
_last_request_time = 0.0
_request_lock = threading.Lock()


def _pace_request(min_interval: float = 1.2) -> None:
    """Enforces minimum interval between API calls to strictly respect provider rate limits."""
    global _last_request_time
    with _request_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()


class APITracker(threading.local):
    def __init__(self):
        self.state = None
        self.publisher = None
        self.current_pid = None


api_tracker = APITracker()


class QuotaError(RuntimeError):
    """The API permanently refuses (persistent 429/403): retrying is useless."""


def post_json(url: str, headers: dict, payload: dict, *, retries: int = 6,
              timeout: int = 60, pause: float = 0.5, name: str = "LLM") -> dict:
    """POST JSON with exponential backoff, respects Retry-After on 429/5xx."""
    last = None

    if api_tracker.state is not None and api_tracker.current_pid is not None:
        if not hasattr(api_tracker.state, "api_status"):
            api_tracker.state.api_status = {}
        api_tracker.state.api_status[str(api_tracker.current_pid)] = {
            "status": "calling",
            "message": f"Calling {name}...",
            "last_update": time.time()
        }
        if api_tracker.publisher:
            api_tracker.publisher.write(api_tracker.state, running=True)

    min_gap = max(pause, 1.2) if pause else 1.2

    for attempt in range(retries):
        try:
            _pace_request(min_gap)
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                detail = (r.text or "").strip()[:300]
                last = f"HTTP {r.status_code} — {detail or 'no detail'}"
                if attempt == retries - 1:
                    break
                # Retry-After takes precedence; otherwise exponential backoff + jitter
                try:
                    wait = float(r.headers.get("Retry-After", 2 ** attempt))
                except (ValueError, TypeError):
                    wait = float(2 ** attempt)
                wait_time = min(wait, MAX_WAIT)

                if api_tracker.state is not None and api_tracker.current_pid is not None:
                    api_tracker.state.api_status[str(api_tracker.current_pid)] = {
                        "status": "rate_limited",
                        "message": f"Pacing requests (retry in {wait_time:.1f}s)...",
                        "last_update": time.time(),
                        "retry_after": wait_time
                    }
                    if api_tracker.publisher:
                        api_tracker.publisher.write(api_tracker.state, running=True)

                time.sleep(wait_time + random.uniform(0, 0.5))
                continue
            r.raise_for_status()
            if pause:
                time.sleep(pause)  # courtesy delay to avoid hitting free tier limits

            if api_tracker.state is not None and api_tracker.current_pid is not None:
                api_tracker.state.api_status[str(api_tracker.current_pid)] = {
                    "status": "idle",
                    "message": "Idle",
                    "last_update": time.time()
                }
                if api_tracker.publisher:
                    api_tracker.publisher.write(api_tracker.state, running=True)

            return r.json()
        except requests.RequestException as e:
            resp_detail = ""
            if getattr(e, "response", None) is not None:
                resp_detail = f" — {e.response.text[:250]}"
            last = f"{e}{resp_detail}"

            if api_tracker.state is not None and api_tracker.current_pid is not None:
                api_tracker.state.api_status[str(api_tracker.current_pid)] = {
                    "status": "network_error",
                    "message": f"Error: {str(e)[:30]}",
                    "last_update": time.time()
                }
                if api_tracker.publisher:
                    api_tracker.publisher.write(api_tracker.state, running=True)

            if getattr(e, "response", None) is not None and e.response.status_code in (400, 401, 403, 404):
                break

            if attempt < retries - 1:
                time.sleep(min(2 ** attempt, MAX_WAIT))

    if api_tracker.state is not None and api_tracker.current_pid is not None:
        api_tracker.state.api_status[str(api_tracker.current_pid)] = {
            "status": "error",
            "message": f"Error: {last[:30]}",
            "last_update": time.time()
        }
        if api_tracker.publisher:
            api_tracker.publisher.write(api_tracker.state, running=True)

    if last and "429" in last:
        raise QuotaError(
            f"{name}: rate limit or quota reached after {retries} attempts.\n"
            f"  API detail: {last}\n"
            f"  Options: wait a few minutes, fall back to --model mistral-small-latest "
            f"(much larger quotas), or increase --pause to slow down calls."
        )
    raise RuntimeError(f"{name} call failed after {retries} attempts: {last}")
