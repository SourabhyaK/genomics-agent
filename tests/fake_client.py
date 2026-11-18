"""
A scripted fake LLM client so we can test the REAL orchestration logic
(task routing, shared state, falsification -> reassignment) without
needing network access or an API key. This is test infrastructure only -
the real run uses AnthropicClient against the actual API.
"""
import json


class FakeClient:
    def __init__(self, script: list[str]):
        """script: a list of canned responses returned in order, one per call."""
        self.script = list(script)
        self.calls = []

    def call(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self.script:
            raise RuntimeError("FakeClient script ran out of responses")
        return self.script.pop(0)


def planner_response(hypotheses: list[dict]) -> str:
    return json.dumps(hypotheses)
