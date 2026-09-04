from app.case_engine import (
    build_initial_progress,
    classify_topic,
    discover_evidence,
    evaluate_accusation,
    public_state,
    validate_case,
)
from app.case_templates import build_fallback_case


def make_case() -> dict:
    return validate_case(build_fallback_case("stable-test-seed"))


def test_fallback_case_is_valid_and_has_unique_culprit() -> None:
    case = make_case()
    assert len(case["suspects"]) == 4
    assert case["culprit_id"] in {item["id"] for item in case["suspects"]}
    for suspect in case["suspects"]:
        truthfulness = {claim["truthfulness"] for claim in suspect["claims"]}
        assert {"TRUTH", "LIE"}.issubset(truthfulness)


def test_public_state_never_exposes_hidden_truth() -> None:
    case = make_case()
    progress = build_initial_progress(case, 18)
    state = public_state("case-1", "ACTIVE", case, progress, "fallback")
    serialized = str(state)
    assert "culprit_id" not in state
    assert case["motive"] not in serialized
    assert case["truth_summary"] not in serialized
    assert all("claims" not in suspect for suspect in state["suspects"])


def test_question_classifier_handles_common_chinese_questions() -> None:
    assert classify_topic("你晚上 8 点在哪里？") == "alibi"
    assert classify_topic("你最后一次见到教授是什么时候？") == "last_seen"
    assert classify_topic("你为什么和他争吵？") == "motive"
    assert classify_topic("门禁记录里有什么异常？") == "evidence"


def test_evidence_discovery_is_rule_driven_and_idempotent() -> None:
    case = make_case()
    found = discover_evidence(case, "alice", "evidence", case["initial_evidence_ids"])
    assert found == ["ev_access"]
    assert discover_evidence(case, "alice", "evidence", case["initial_evidence_ids"] + found) == []


def test_accusation_requires_correct_suspect_and_proof_group() -> None:
    case = make_case()
    solved, missing = evaluate_accusation(
        case, "bob", ["ev_access", "ev_requisition", "ev_vial"]
    )
    assert solved == "SOLVED"
    assert missing == []

    insufficient, _ = evaluate_accusation(case, "bob", ["ev_access", "ev_vial"])
    assert insufficient == "INSUFFICIENT"

    wrong, _ = evaluate_accusation(
        case, "alice", ["ev_access", "ev_requisition", "ev_vial"]
    )
    assert wrong == "WRONG"

