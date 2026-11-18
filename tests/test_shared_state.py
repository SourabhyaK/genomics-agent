import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.shared_state import EvidenceLog, Hypothesis, HypothesisStatus


def test_add_hypothesis_logs_event():
    log = EvidenceLog()
    log.add_hypothesis(Hypothesis(id="h1", description="test hypothesis"))
    assert "h1" in log.hypotheses
    assert len(log.events) == 1
    assert "h1" in log.events[0][1]


def test_unresolved_hypotheses_excludes_verified():
    log = EvidenceLog()
    log.add_hypothesis(Hypothesis(id="h1", description="a"))
    log.add_hypothesis(Hypothesis(id="h2", description="b"))
    log.verify("h1", verified=True, notes="confirmed")
    unresolved = log.unresolved_hypotheses()
    assert len(unresolved) == 1
    assert unresolved[0].id == "h2"


def test_unresolved_hypotheses_excludes_falsified():
    log = EvidenceLog()
    log.add_hypothesis(Hypothesis(id="h1", description="a"))
    log.verify("h1", verified=False, notes="falsified")
    assert log.unresolved_hypotheses() == []
    assert log.hypotheses["h1"].status == HypothesisStatus.FALSIFIED


def test_verified_explanation_returns_none_if_none_verified():
    log = EvidenceLog()
    log.add_hypothesis(Hypothesis(id="h1", description="a"))
    assert log.verified_explanation() is None


def test_verified_explanation_returns_the_verified_one():
    log = EvidenceLog()
    log.add_hypothesis(Hypothesis(id="h1", description="a"))
    log.add_hypothesis(Hypothesis(id="h2", description="b"))
    log.verify("h1", verified=False, notes="no")
    log.verify("h2", verified=True, notes="yes")
    result = log.verified_explanation()
    assert result.id == "h2"


def test_record_evidence_marks_supported():
    log = EvidenceLog()
    log.add_hypothesis(Hypothesis(id="h1", description="a"))
    log.record_evidence("h1", "found something")
    assert log.hypotheses["h1"].status == HypothesisStatus.SUPPORTED
    assert "found something" in log.hypotheses["h1"].evidence
