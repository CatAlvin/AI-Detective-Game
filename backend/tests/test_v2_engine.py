from app.case_engine import (
    build_answer_plan,
    build_initial_progress,
    build_result,
    discover_evidence,
    evaluate_accusation,
    interpret_question,
    public_evidence,
    review_accusation,
    validate_case,
)
from app.case_templates import build_fallback_case


def make_case() -> dict:
    return validate_case(build_fallback_case("v2-stable-seed"))


def suspect(case: dict, npc_id: str) -> dict:
    return next(item for item in case["suspects"] if item["id"] == npc_id)


def test_v2_case_is_enriched_before_freeze() -> None:
    case = make_case()
    assert case["schema_version"] == "2.0"
    assert case["engine_version"] == "truth-dialogue-v2"
    assert case["facts"]
    assert all(item["kind"] for item in case["evidence"])
    assert all(item["investigation_type"] for item in case["evidence"])
    assert {"motive", "method", "opportunity"}.issubset(
        set(case["proof_rule"]["required_dimensions"])
    )


def test_exact_time_question_does_not_replay_a_different_time_window() -> None:
    case = make_case()
    progress = build_initial_progress(case, 18)
    alice = suspect(case, "alice")
    frame = interpret_question("晚上 8 点左右你在哪里？", [], [])
    plan = build_answer_plan(case, alice, frame, progress)
    # Alice's 19:50–20:15 alibi covers 20:00, so the direct claim is allowed.
    assert plan["coverage"] == "DIRECT"
    assert "19:50" in plan["draft"]

    frame = interpret_question("晚上 9 点左右你在哪里？", [], [])
    plan = build_answer_plan(case, alice, frame, progress)
    assert plan["coverage"] == "PARTIAL"
    assert "你问的是 21:00 左右" in plan["draft"]
    assert "不能证明你所问的那个时间点" in plan["draft"]


def test_witness_and_account_intents_are_not_routed_to_generic_evidence() -> None:
    case = make_case()
    progress = build_initial_progress(case, 18)
    bob = suspect(case, "bob")
    witness_frame = interpret_question("有什么目击者吗？", [], [])
    witness_plan = build_answer_plan(case, bob, witness_frame, progress)
    assert witness_frame["intent"] == "WITNESS"
    assert "目击" in witness_plan["draft"] or "作证" in witness_plan["draft"]

    progress["discovered_evidence_ids"].append("ev_requisition")
    progress["evidence_states"]["ev_requisition"] = "VERIFIED"
    account_frame = interpret_question("这份领用单的登录账号是你的？", ["ev_requisition"], [])
    account_plan = build_answer_plan(case, bob, account_frame, progress)
    assert account_frame["intent"] == "ACCOUNT"
    assert "账号" in account_plan["draft"]
    assert "实际操作者" in account_plan["draft"]


def test_discovered_material_starts_as_lead_until_verified() -> None:
    case = make_case()
    progress = build_initial_progress(case, 18)
    found = discover_evidence(case, "alice", "evidence", progress["discovered_evidence_ids"])
    assert found == ["ev_access"]
    progress["discovered_evidence_ids"].extend(found)
    lead = public_evidence(case, found, progress["evidence_states"])[0]
    assert lead["verification_state"] == "UNVERIFIED"
    assert lead["dimensions"] == []
    assert not lead["usable_in_accusation"]

    progress["evidence_states"]["ev_access"] = "VERIFIED"
    verified = public_evidence(case, found, progress["evidence_states"])[0]
    assert verified["verification_state"] == "VERIFIED"
    assert "opportunity" in verified["dimensions"]
    assert verified["usable_in_accusation"]


def test_review_never_discloses_whether_suspect_is_correct() -> None:
    case = make_case()
    theory = {
        "motive": ["ev_requisition"],
        "method": ["ev_vial"],
        "opportunity": ["ev_access"],
    }
    review = review_accusation(case, ["ev_requisition", "ev_vial", "ev_access"], theory)
    assert all(review["coverage"].values())
    assert "culprit" not in str(review).lower()
    assert case["culprit_id"] not in str(review)


def test_structured_accusation_and_personalized_result() -> None:
    case = make_case()
    theory = {
        "motive": ["ev_requisition"],
        "method": ["ev_vial"],
        "opportunity": ["ev_access"],
    }
    selected = ["ev_requisition", "ev_vial", "ev_access"]
    outcome, missing = evaluate_accusation(case, "bob", selected, theory)
    assert outcome == "SOLVED"
    assert missing == []
    result = build_result(case, outcome, selected, missing, build_initial_progress(case, 18), theory)
    assert len(result["evidence_analysis"]) == 3
    assert result["player_theory"] == theory
    assert all(item["discovery_status"] in {"CAUGHT", "HEARD", "MISSED"} for item in result["key_lies"])
