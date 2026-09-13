import json
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.llm.factory import create_chat_model
from app.llm.rate_limit import CloudRequestPacer, transient_error, provider_error_message

PROMPTS = Path(__file__).resolve().parents[1] / "agents" / "prompts"


class ModelOutputError(RuntimeError):
    pass


def parse_json(text: str, schema: type[BaseModel]):
    if len(text) > 32000:
        raise ValueError("Model output exceeds maximum size")
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return schema.model_validate(json.loads(text))


class ModelGateway:
    def __init__(self, budget, guard=lambda: None, model=None):
        self.budget, self.guard, self.model = budget, guard, model

    def generate(self, role: str, payload: dict, schema: type[BaseModel]):
        system = (PROMPTS / "base.md").read_text() + "\n" + (PROMPTS / f"{role}.md").read_text()
        system += "\nReturn exactly one JSON object matching this schema:\n" + json.dumps(schema.model_json_schema())
        content = json.dumps(payload, ensure_ascii=False, default=str)
        if len(system) + len(content) > settings.RCA_MAX_CONTEXT_CHARS:
            raise ModelOutputError("Context exceeds the configured input budget")
        messages = [SystemMessage(content=system), HumanMessage(content=content)]
        for attempt in range(2):
            self.guard()
            for request_attempt in range(settings.LLM_MAX_ATTEMPTS):
                self.budget.take("llm")
                if self.model is None and settings.REASONING_PROVIDER == "cloud":
                    CloudRequestPacer.wait(self.budget)
                self.guard()
                timeout = settings.LOCAL_LLM_TIMEOUT_SECONDS if settings.REASONING_PROVIDER == "local" else settings.LLM_TIMEOUT_SECONDS
                model = self.model or create_chat_model(timeout=min(timeout, self.budget.remaining_seconds()),
                                                        json_schema=schema.model_json_schema(), action=schema.__name__ == "AgentAction")
                try:
                    response = model.invoke(messages)
                    break
                except Exception as exc:
                    if not transient_error(exc) or request_attempt + 1 == settings.LLM_MAX_ATTEMPTS:
                        raise ModelOutputError(provider_error_message(exc)) from exc
                    delay = min(2 ** (request_attempt + 1), self.budget.remaining_seconds())
                    time.sleep(delay)
            self.guard()
            self.budget.check()
            text = response.content
            if isinstance(text, list):
                text = "".join(b.get("text", "") for b in text if isinstance(b, dict) and b.get("type") == "text")
            try:
                return parse_json(text, schema)
            except (ValidationError, ValueError, TypeError, IndexError, RecursionError) as exc:
                if attempt:
                    raise ModelOutputError("Model returned invalid structured output after one repair") from exc
                # Bounded repair without copying a potentially huge invalid response.
                messages.append(HumanMessage(content="Your output was invalid. Return only valid JSON using the exact schema. Validation: " + str(exc)[:350]))
        raise ModelOutputError("No valid output")
