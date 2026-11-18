"""
Orchestrates the full swarm: Planner -> parallel Explorers -> Verifier,
with reassignment when a hypothesis is falsified, under a step budget.

Also provides the real Anthropic client wrapper (AnthropicClient) used
when actually running this against the API on your machine.
"""
import time
from src.shared_state import EvidenceLog, Hypothesis, HypothesisStatus
from src.agents import Planner, Explorer, Verifier


class NIMClient:
    """Real wrapper around NVIDIA NIM (build.nvidia.com) - runs the agents'
    reasoning on NVIDIA's own hosted inference platform, through NVIDIA's
    AI Science Factory, not a third-party API. Requires `pip install openai`
    (NIM's API is OpenAI-compatible) and an NVIDIA_API_KEY environment
    variable (free account + free credits at build.nvidia.com). Only
    instantiate this when actually running for real - the test suite uses
    FakeClient instead so it needs no network or API key."""

    def __init__(self, model: str = "meta/llama-3.3-70b-instruct"):
        import os
        from openai import OpenAI
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.environ["NVIDIA_API_KEY"],
        )
        self.model = model

    def call(self, system: str, user: str) -> str:
        import time
        last_error = None
        for attempt in range(5):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                body = getattr(getattr(e, "response", None), "text", None)
                print(f"  [NIM call failed, attempt {attempt+1}/5: {type(e).__name__}]")
                print(f"  [Full error body: {body if body else str(e)}]")
                wait = 10 * (attempt + 1)  # 10, 20, 30, 40, 50 seconds - slower backoff
                print(f"  [Retrying in {wait}s...]")
                time.sleep(wait)
        raise RuntimeError(f"NIM call failed after 5 retries. Last error: {last_error}")


class GroqClient:
    """Real wrapper around Groq's free API (console.groq.com) - no credit
    card required, OpenAI-compatible, and generally fast and stable.
    Requires `pip install openai` and a GROQ_API_KEY environment variable."""

    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        import os
        from openai import OpenAI
        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ["GROQ_API_KEY"],
        )
        self.model = model

    def call(self, system: str, user: str) -> str:
        import time
        last_error = None
        for attempt in range(5):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                print(f"  [Groq call failed, attempt {attempt+1}/5: {type(e).__name__}. "
                      f"Retrying in {wait}s...]")
                time.sleep(wait)
        raise RuntimeError(f"Groq call failed after 5 retries. Last error: {last_error}")


class AnthropicClient:
    """Thin real wrapper around the Anthropic SDK, kept as an alternative
    backend - swap NIMClient for AnthropicClient anywhere below with no
    other code changes, since both implement the same .call(system, user)
    interface. Requires `pip install anthropic` and an ANTHROPIC_API_KEY
    environment variable."""

    def __init__(self, model: str = "claude-sonnet-4-5"):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = model

    def call(self, system: str, user: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text


def run_swarm(vcf_path: str, published_count: int, task_description: str,
              client, max_steps: int = 10) -> tuple[EvidenceLog, int]:
    """Returns (final evidence log, number of steps taken)."""
    log = EvidenceLog()
    planner = Planner(client)
    verifier = Verifier(client)

    hypotheses = planner.propose_hypotheses(task_description)
    for h in hypotheses:
        log.add_hypothesis(h)
    log.step_count += 1

    explorer_pool = [Explorer(client, f"explorer-{i}") for i in range(len(hypotheses))]

    while log.unresolved_hypotheses() and log.step_count < max_steps:
        unresolved = log.unresolved_hypotheses()
        for hyp, explorer in zip(unresolved, explorer_pool):
            hyp.status = HypothesisStatus.UNDER_INVESTIGATION
            hyp.assigned_agent = explorer.agent_id
            evidence = explorer.investigate(hyp, vcf_path, published_count)
            log.record_evidence(hyp.id, evidence)
            log.step_count += 1

            verified, notes = verifier.verify(hyp, vcf_path, published_count)
            log.verify(hyp.id, verified, notes)
            log.step_count += 1

            if verified:
                return log, log.step_count
        # If nothing verified this round, remaining unresolved hypotheses
        # get reassigned to the next round automatically (they're still
        # in `unresolved_hypotheses()` since they weren't marked verified).

    return log, log.step_count


def run_single_agent_baseline(vcf_path: str, published_count: int,
                               task_description: str, client, max_steps: int = 10) -> tuple[str, int]:
    """A single agent attempting the same task alone, no coordination,
    no independent verification step - for the controlled comparison."""
    from src.vcf_evidence import find_extra_variants
    import json
    evidence = find_extra_variants(vcf_path, published_count)
    response = client.call(
        system=("You are a researcher investigating a real discrepancy in a "
                "variant-calling pipeline. Propose and check hypotheses "
                "yourself, one at a time, using the evidence provided. "
                "State your final conclusion clearly when confident."),
        user=f"{task_description}\nEvidence: {json.dumps(evidence, default=str)}",
    )
    return response, 1  # single call, no multi-step coordination to count
