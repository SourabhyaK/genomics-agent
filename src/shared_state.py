"""
Shared state for the agent swarm: a single evidence log every agent reads
from and writes to, so the Verifier can see what's already been checked
and the Planner can reassign work without duplicating it.
"""
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class HypothesisStatus(Enum):
    PROPOSED = "proposed"
    UNDER_INVESTIGATION = "under_investigation"
    SUPPORTED = "supported"       # Explorer found evidence for it
    VERIFIED = "verified"         # Verifier independently re-derived it
    FALSIFIED = "falsified"       # Verifier checked it and it's wrong


@dataclass
class Hypothesis:
    id: str
    description: str
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    assigned_agent: str | None = None
    evidence: list[str] = field(default_factory=list)
    verifier_notes: str | None = None


@dataclass
class EvidenceLog:
    """The single shared source of truth for the whole swarm run."""
    hypotheses: dict[str, Hypothesis] = field(default_factory=dict)
    events: list[tuple[datetime, str]] = field(default_factory=list)
    step_count: int = 0

    def log(self, message: str) -> None:
        self.events.append((datetime.now(), message))

    def add_hypothesis(self, hyp: Hypothesis) -> None:
        self.hypotheses[hyp.id] = hyp
        self.log(f"Hypothesis proposed: {hyp.id} — {hyp.description}")

    def record_evidence(self, hyp_id: str, evidence: str) -> None:
        self.hypotheses[hyp_id].evidence.append(evidence)
        self.hypotheses[hyp_id].status = HypothesisStatus.SUPPORTED
        self.log(f"Evidence recorded for {hyp_id}: {evidence}")

    def verify(self, hyp_id: str, verified: bool, notes: str) -> None:
        hyp = self.hypotheses[hyp_id]
        hyp.verifier_notes = notes
        hyp.status = HypothesisStatus.VERIFIED if verified else HypothesisStatus.FALSIFIED
        self.log(f"Verifier {'CONFIRMED' if verified else 'FALSIFIED'} {hyp_id}: {notes}")

    def unresolved_hypotheses(self) -> list[Hypothesis]:
        return [h for h in self.hypotheses.values()
                if h.status in (HypothesisStatus.PROPOSED, HypothesisStatus.UNDER_INVESTIGATION)]

    def verified_explanation(self) -> Hypothesis | None:
        for h in self.hypotheses.values():
            if h.status == HypothesisStatus.VERIFIED:
                return h
        return None
