"""
The real experiment: run the swarm and the single-agent baseline against
your actual VCF discrepancy, using NVIDIA NIM. Run this after:
  1. Copying your real SRR2584866_final_variants.vcf into this folder
  2. export NVIDIA_API_KEY="nvapi-..."
"""
import sys
sys.path.insert(0, ".")

from src.swarm_runner import NIMClient, run_swarm, run_single_agent_baseline

VCF_PATH = "SRR2584866_final_variants.vcf"
PUBLISHED_COUNT = 766
TASK = ("This VCF has more variants than the published benchmark for this "
        "sample (766). Investigate why.")

client = NIMClient(model="nvidia/nemotron-3.5-bolt-e4b")

print("=" * 70)
print("RUNNING SWARM")
print("=" * 70)
swarm_log, swarm_steps = run_swarm(
    vcf_path=VCF_PATH, published_count=PUBLISHED_COUNT,
    task_description=TASK, client=client,
)
final = swarm_log.verified_explanation()
print(f"\nSwarm finished in {swarm_steps} steps.")
if final:
    print(f"Verified explanation: {final.description}")
    print(f"Verifier notes: {final.verifier_notes}")
else:
    print("No hypothesis was verified - all were falsified or budget ran out.")
    print("(This is still a legitimate result: an evidence-based narrowing of the cause.)")

print("\nAll hypotheses considered:")
for h in swarm_log.hypotheses.values():
    print(f"  [{h.status.value}] {h.id}: {h.description}")
    print(f"    Verifier notes: {h.verifier_notes}")

print("\n" + "=" * 70)
print("RUNNING SINGLE-AGENT BASELINE")
print("=" * 70)
baseline_response, baseline_steps = run_single_agent_baseline(
    vcf_path=VCF_PATH, published_count=PUBLISHED_COUNT,
    task_description=TASK, client=client,
)
print(f"\nSingle agent finished in {baseline_steps} step.")
print(f"Conclusion: {baseline_response}")

print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)
verified_word = "yes" if final else "no"
print(f"Swarm: {swarm_steps} steps, independently verified={verified_word}")
print(f"Single agent: {baseline_steps} step, no independent verification step exists")
