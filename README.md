# Agent Swarms for Diagnosing a Real Genomic Discrepancy

Built for the NVIDIA Applied Research Scientist Intern, Agentic Biology application.

## The real question

My own [variant-calling pipeline](https://github.com/SourabhyaK/variant-calling),
validated via Docker, found **775 variants** in sample SRR2584866 against a
**published benchmark of 766** — a 9-variant discrepancy I never diagnosed.
This project uses a multi-agent swarm to investigate it, with a controlled
comparison against a single agent working alone.

## Architecture

- **Planner** — proposes 2-4 falsifiable hypotheses for the discrepancy
- **Explorer agents** (run per-hypothesis) — gather real evidence using
  deterministic tools (`src/vcf_evidence.py`) that parse the actual VCF file
- **Verifier** — does NOT trust an Explorer's conclusion; re-derives the
  evidence independently and marks the hypothesis VERIFIED or FALSIFIED
- **Shared evidence log** (`src/shared_state.py`) — all agents read/write
  here, so falsified hypotheses are abandoned and the swarm doesn't stall
- **Single-agent baseline** (`run_single_agent_baseline`) — same task, no
  coordination, no independent verification step, for the controlled comparison

## What's verified right now vs. what needs your API key

**Fully real and tested, no API needed:**
- `src/vcf_evidence.py` — real VCF parsing and evidence-gathering logic
- `src/shared_state.py` — the evidence log and hypothesis tracking
- The full orchestration control flow (`src/swarm_runner.py`), including the
  falsify-and-reassign loop, tested end-to-end with a scripted fake client
  (`tests/fake_client.py`) standing in for the LLM
- **17/17 tests pass**, covering real VCF data handling and the real
  control-flow logic (see `tests/`)

**Needs `pip install openai` + a free `NVIDIA_API_KEY` to run for real:**
- The actual LLM reasoning inside the Planner/Explorer/Verifier calls,
  running on NVIDIA NIM (build.nvidia.com) - NVIDIA's own hosted inference
  platform, not a third-party API
- Running against your real discrepancy data instead of the test fixture

## Running it for real

```bash
pip install openai
```

Get a free API key (with free credits) at [build.nvidia.com](https://build.nvidia.com) -
sign in, open any model card (e.g. Llama 3.3 70B Instruct), click "Get API Key."

```bash
export NVIDIA_API_KEY="nvapi-your-key-here"
```

(An `AnthropicClient` alternative is also included in `src/swarm_runner.py`
if you'd rather use Claude - same `.call()` interface, drop-in swap, just
needs `pip install anthropic` and `ANTHROPIC_API_KEY` instead.)

Point it at your real data (copy your actual
`variant-calling/results/vcf/SRR2584866_final_variants.vcf` into this repo), then:

```python
from src.swarm_runner import NIMClient, run_swarm, run_single_agent_baseline

client = NIMClient()

swarm_log, swarm_steps = run_swarm(
    vcf_path="SRR2584866_final_variants.vcf",
    published_count=766,
    task_description="This VCF has 775 variants but the published benchmark for "
                      "this sample reports 766. Investigate why.",
    client=client,
)
print(swarm_log.verified_explanation())
print(f"Swarm took {swarm_steps} steps")

baseline_response, baseline_steps = run_single_agent_baseline(
    vcf_path="SRR2584866_final_variants.vcf",
    published_count=766,
    task_description="Same task as above.",
    client=client,
)
print(baseline_response)
```

Run both, compare: did the swarm's verified explanation actually hold up
under independent re-checking? Did the single agent's unverified conclusion
match? How many steps did each take? That comparison is the actual result
to report.

## Running the test suite

```bash
pip install pytest
cd agent_swarm
python3 -m pytest tests/ -v
```
