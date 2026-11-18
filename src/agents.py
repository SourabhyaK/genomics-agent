"""
Planner, Explorer, and Verifier agents. Each wraps a real call to the
Anthropic API. The LLM client is injected (not hardcoded) specifically so
the orchestration logic can be tested with a fake client here, and run
for real with `anthropic.Anthropic()` on your machine.
"""
import json
from src.shared_state import EvidenceLog, Hypothesis, HypothesisStatus
from src.vcf_evidence import (
    count_variants, variants_by_quality_threshold,
    variants_near_position, find_extra_variants, classify_all_extra_variants,
)

PLANNER_SYSTEM_PROMPT = """You are the Planner agent investigating a real \
discrepancy: a variant-calling pipeline found more variants than a published \
benchmark reported for the same sample. Propose 2-4 distinct, falsifiable \
hypotheses for why. Respond ONLY as a JSON list of objects: \
[{"id": "...", "description": "..."}]"""

EXPLORER_SYSTEM_PROMPT = """You are an Explorer agent. You have been assigned \
ONE hypothesis to investigate using the provided tools. Call the tool that \
would gather the most relevant evidence, then summarize what you found in \
one or two sentences. Be honest if the evidence does NOT support the \
hypothesis - do not force a conclusion."""

VERIFIER_SYSTEM_PROMPT = """You are the Verifier agent. You do not trust an \
Explorer's conclusion just because it was stated - you re-run the relevant \
check yourself against the raw evidence and decide independently whether \
the hypothesis is actually supported. You are given the TYPE of every single \
one of the extra variants (not just one example), so a hypothesis about \
variant type (e.g., 'these are INDELs' or 'these are multi-allelic') is only \
VERIFIED if it holds for ALL of them, not just some. If the types are mixed, \
say so explicitly and do not verify a single-type hypothesis. Respond with \
VERIFIED or FALSIFIED and one sentence of justification grounded in the \
actual counts you see."""


class Planner:
    def __init__(self, client):
        self.client = client

    def propose_hypotheses(self, task_description: str) -> list[Hypothesis]:
        response = self.client.call(
            system=PLANNER_SYSTEM_PROMPT,
            user=task_description,
        )
        raw = json.loads(response)
        return [Hypothesis(id=h["id"], description=h["description"]) for h in raw]


class Explorer:
    TOOLS = {
        "count_variants": count_variants,
        "variants_by_quality_threshold": variants_by_quality_threshold,
        "variants_near_position": variants_near_position,
        "find_extra_variants": find_extra_variants,
    }

    def __init__(self, client, agent_id: str):
        self.client = client
        self.agent_id = agent_id

    def investigate(self, hypothesis: Hypothesis, vcf_path: str, published_count: int) -> str:
        """Real tool call first (deterministic, no LLM needed for the data
        itself), then the LLM summarizes what the real numbers show."""
        extra = find_extra_variants(vcf_path, published_count)
        tool_result = json.dumps(extra, default=str)
        response = self.client.call(
            system=EXPLORER_SYSTEM_PROMPT,
            user=f"Hypothesis: {hypothesis.description}\nTool result: {tool_result}",
        )
        return response


class Verifier:
    def __init__(self, client):
        self.client = client

    def verify(self, hypothesis: Hypothesis, vcf_path: str, published_count: int) -> tuple[bool, str]:
        """Re-derives evidence independently rather than trusting the
        Explorer's summary - calls the real tool again itself, and for
        type-based hypotheses, classifies ALL extra variants (not just one)
        so a 'they're all X type' claim is checked against the full set."""
        fresh_check = classify_all_extra_variants(vcf_path, published_count)
        response = self.client.call(
            system=VERIFIER_SYSTEM_PROMPT,
            user=(f"Hypothesis: {hypothesis.description}\n"
                  f"Explorer's claimed evidence: {hypothesis.evidence}\n"
                  f"My independent re-check of ALL {fresh_check['n_extra']} extra variants: "
                  f"{json.dumps(fresh_check, default=str)}"),
        )
        verified = response.strip().upper().startswith("VERIFIED")
        return verified, response
