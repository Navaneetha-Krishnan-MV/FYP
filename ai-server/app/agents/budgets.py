from dataclasses import dataclass, field
import time

from app.config import settings


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Budget:
    llm_calls: int = 0
    tool_calls: int = 0
    started: float = field(default_factory=time.monotonic)

    def check(self):
        if time.monotonic() - self.started >= settings.RCA_MAX_SECONDS:
            raise BudgetExceeded("Investigation deadline reached")

    def take(self, kind: str):
        self.check()
        attr, limit = ("llm_calls", settings.RCA_MAX_LLM_CALLS) if kind == "llm" else ("tool_calls", settings.RCA_MAX_TOOL_CALLS)
        if getattr(self, attr) >= limit:
            raise BudgetExceeded(f"{kind} call budget reached")
        setattr(self, attr, getattr(self, attr) + 1)

    def remaining_seconds(self):
        self.check()
        return max(0.1, settings.RCA_MAX_SECONDS - (time.monotonic() - self.started))

    def usage(self):
        return {"llm_calls": self.llm_calls, "tool_calls": self.tool_calls,
                "elapsed_seconds": round(time.monotonic() - self.started, 2)}
