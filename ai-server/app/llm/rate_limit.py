import threading
import time
import httpx

from app.agents.budgets import BudgetExceeded
from app.config import settings


class CloudRequestPacer:
    _lock = threading.Lock()
    _next_at = 0.0

    @classmethod
    def wait(cls, budget):
        with cls._lock:
            delay = max(0, cls._next_at - time.monotonic())
            if delay >= budget.remaining_seconds():
                raise BudgetExceeded("Deadline would be exceeded while waiting for cloud quota")
            if delay:
                time.sleep(delay)
            cls._next_at = time.monotonic() + 60 / settings.CLOUD_REASONING_REQUESTS_PER_MINUTE


def transient_error(exc):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if "GenerateRequestsPerDay" in str(exc):
            return False
        status = getattr(exc, "code", getattr(exc, "status_code", None))
        if status in {408, 429, 500, 502, 503, 504} or isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError)):
            return True
        exc = exc.__cause__
    return False


def provider_error_message(exc):
    if "GenerateRequestsPerDay" in str(exc):
        return "Cloud reasoning daily quota is exhausted. Retry after quota resets or select local reasoning."
    if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
        return "Cloud reasoning quota was exceeded after bounded retries. Check the configured request rate."
    return "Reasoning provider request failed after bounded retries; check model availability and service logs."
