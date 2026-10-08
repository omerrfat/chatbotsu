"""LLM provider wrapper. Everything else talks to `get_provider()` only."""
import os
import re


class LLMProvider:
    def complete(self, system: str, messages: list[dict]) -> str:
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    def __init__(self):
        import anthropic

        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.model = os.getenv("LLM_MODEL", "claude-haiku-5-5")

    def complete(self, system, messages):
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "500")),
            system=system,
            messages=messages,
        )
        return "".join(b.text for b in resp.content if b.type == "text")


class MockProvider(LLMProvider):
    """Offline stand-in so the whole pipeline runs without an API key.

    Matches the customer's words against the FAQ in the system prompt and
    hands off otherwise. Good enough for plumbing tests, NOT for judging
    real bot quality.
    """

    def complete(self, system, messages):
        import json

        text = messages[-1]["content"].lower()
        if re.search(r"\b(human|person|manager|owner|staff|refund|complain)\b", text):
            return json.dumps({"reply": "I'll ask a staff member to follow up with you.",
                               "handoff": True, "handoff_reason": "customer asked for a person", "lead": None})
        words = {w for w in re.findall(r"[a-z]{4,}", text)}
        best, best_score = None, 0
        for m in re.finditer(r"Q: (.+)\nA: (.+)", system):
            score = len(words & set(re.findall(r"[a-z]{4,}", m.group(1).lower())))
            if score > best_score:
                best, best_score = m.group(2), score
        if best:
            return json.dumps({"reply": best, "handoff": False, "handoff_reason": "", "lead": None})
        return json.dumps({"reply": "I don't have that information, so I'll ask the team to follow up with you.",
                           "handoff": True, "handoff_reason": "not in knowledge base", "lead": None})


def get_provider() -> LLMProvider:
    name = os.getenv("LLM_PROVIDER", "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "mock")
    return AnthropicProvider() if name == "anthropic" else MockProvider()
