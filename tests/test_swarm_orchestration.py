import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.swarm_runner import run_swarm, run_single_agent_baseline
from src.shared_state import HypothesisStatus
from tests.fake_client import FakeClient, planner_response

FIXTURE = os.path.join(os.path.dirname(__file__), "fixture.vcf")


def test_swarm_falsifies_first_hypothesis_then_verifies_second():
    """The core claim this project makes: when the Verifier falsifies a
    hypothesis, the swarm moves on to the next one instead of stalling -
    and the FINAL verified explanation is the one that actually held up,
    not just the first one proposed."""
    script = [
        planner_response([
            {"id": "h1", "description": "Tool version difference caused extra calls"},
            {"id": "h2", "description": "Extra variants are low-QUAL calls near a threshold"},
        ]),
        "Explored hypothesis 1: inconclusive from the data alone.",
        "FALSIFIED: the variant positions don't correspond to any known tool-version-sensitive region.",
        "Explored hypothesis 2: the extra variants are clustered at low QUAL scores.",
        "VERIFIED: independently re-checked - the 3 extra variants are the lowest-QUAL calls, consistent with a threshold effect.",
    ]
    client = FakeClient(script)

    log, steps = run_swarm(
        vcf_path=FIXTURE,
        published_count=3,
        task_description="Why does this VCF have more variants than published?",
        client=client,
        max_steps=10,
    )

    assert log.hypotheses["h1"].status == HypothesisStatus.FALSIFIED
    assert log.hypotheses["h2"].status == HypothesisStatus.VERIFIED
    final = log.verified_explanation()
    assert final is not None
    assert final.id == "h2"
    assert steps == 5  # 1 planner call + (investigate+verify) x 2 hypotheses


def test_swarm_returns_none_if_all_hypotheses_falsified():
    script = [
        planner_response([{"id": "h1", "description": "wrong guess"}]),
        "Explored: no clear signal.",
        "FALSIFIED: does not match the evidence.",
    ]
    client = FakeClient(script)

    log, steps = run_swarm(
        vcf_path=FIXTURE, published_count=3,
        task_description="test", client=client, max_steps=10,
    )
    assert log.verified_explanation() is None
    assert log.hypotheses["h1"].status == HypothesisStatus.FALSIFIED


def test_single_agent_baseline_runs_one_call_no_coordination():
    client = FakeClient(["My conclusion: the extra variants are low-QUAL artifacts."])
    response, steps = run_single_agent_baseline(
        vcf_path=FIXTURE, published_count=3,
        task_description="test", client=client,
    )
    assert steps == 1
    assert "conclusion" in response.lower()
    assert len(client.calls) == 1  # confirms no multi-step coordination happened
