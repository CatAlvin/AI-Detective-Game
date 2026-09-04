from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any


REQUIRED_TOPICS = {
    "alibi", "relationship", "last_seen", "motive",
    "method", "evidence", "secret", "general",
}
VALID_STANCES = {"TRUTH", "LIE", "EVASIVE", "UNKNOWN"}
DIMENSION_LABELS = {
    "opportunity": "作案机会",
    "method": "作案手段",
    "motive": "作案动机",
    "contradiction": "口供矛盾",
    "identity": "身份关联",
    "causality": "因果连接",
}
EVIDENCE_STATE_LABELS = {
    "UNVERIFIED": "未核实",
    "REQUESTED": "调取中",
    "VERIFIED": "已核验",
    "CONTESTED": "存在冲突",
    "INVALIDATED": "已排除",
}
PRESSURE_STATES = ("CALM", "GUARDED", "DEFENSIVE", "UNSTEADY")

INTENT_TOPIC_MAP = {
    "ALIBI": "alibi",
    "LAST_SEEN": "last_seen",
    "RELATIONSHIP": "relationship",
    "MOTIVE": "motive",
    "METHOD": "method",
    "EVIDENCE": "evidence",
    "SECRET": "secret",
    "WITNESS": "alibi",
    "ACCOUNT": "evidence",
    "PERMISSION": "method",
    "GENERAL": "general",
}
INTENT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("WITNESS", ("目击者", "证人", "谁能证明", "有人作证", "谁看见", "还有谁", "谁能接触", "witness")),
    ("ACCOUNT", ("账号", "登录名", "账户", "工牌", "account", "login")),
    ("PERMISSION", ("权限", "授权", "能不能修改", "有权", "permission", "access right")),
    ("SECRET", ("秘密", "隐瞒", "瞒着", "没说", "secret", "hide")),
    ("LAST_SEEN", ("最后见", "最后一次见", "上次见", "见到死者", "见过教授", "谈了什么", "last saw")),
    ("RELATIONSHIP", ("关系", "认识", "相处", "关系如何", "relationship", "know the victim")),
    ("MOTIVE", ("动机", "为什么", "冲突", "争吵", "论文", "利益", "motive", "reason")),
    ("METHOD", ("怎么死", "死因", "凶器", "手段", "试剂", "毒", "咖啡", "method", "weapon")),
    ("EVIDENCE", ("证据", "门禁", "监控", "记录", "物证", "线索", "排程", "日志", "evidence")),
    ("ALIBI", ("几点", "在哪里", "去哪", "时间线", "不在场", "晚上", "整晚", "当时", "案发时", "where", "when")),
]


class CaseValidationError(ValueError):
    pass


def _infer_evidence_kind(source: str, title: str) -> str:
    normalized = f"{source}{title}"
    if any(item in normalized for item in ("门禁", "日志", "系统", "监控", "手表", "记录", "排程")):
        return "DIGITAL_RECORD"
    if any(item in normalized for item in ("目击", "补述", "证词")):
        return "WITNESS_OBSERVATION"
    if any(item in normalized for item in ("报告", "检验", "分析", "复验")):
        return "ANALYSIS_RESULT"
    return "PHYSICAL_EVIDENCE"


def _investigation_type(kind: str) -> str:
    if kind == "DIGITAL_RECORD":
        return "REQUEST_RECORD"
    if kind in {"ANALYSIS_RESULT", "PHYSICAL_EVIDENCE"}:
        return "FORENSIC_CHECK"
    return "VERIFY_WITNESS"


def _action_label(action_type: str) -> str:
    return {
        "REQUEST_RECORD": "调取原始记录",
        "FORENSIC_CHECK": "提交复验",
        "VERIFY_WITNESS": "交叉核实",
        "INSPECT_SCENE": "勘查现场",
    }.get(action_type, "核验来源")


def _upgrade_case_v2(case: dict[str, Any]) -> dict[str, Any]:
    """Enrich V1-compatible generated cases before the immutable snapshot is frozen."""
    case["schema_version"] = "2.0"
    case["engine_version"] = "truth-dialogue-v2"
    if not case.get("facts"):
        case["facts"] = [
            {
                "id": f"fact_timeline_{index + 1}",
                "kind": "EVENT",
                "time": item.get("time", ""),
                "content": item.get("event", ""),
            }
            for index, item in enumerate(case.get("truth_timeline", []))
        ]

    for suspect in case.get("suspects", []):
        claims = suspect.get("claims", [])
        suspect.setdefault(
            "persona_style",
            {
                "voice": suspect.get("personality", "克制、简洁"),
                "under_pressure": "被追问时先回应质疑，再坚持或收窄原有说法",
                "forbidden": "不得使用其他嫌疑人的口头禅，不得主动泄露隐藏事实",
            },
        )
        suspect.setdefault(
            "knowledge_profile",
            {
                "claim_ids": [claim.get("id") for claim in claims if claim.get("id")],
                "unknown_policy": "对不在已知事实和口供中的细节明确表示不知道或无法确认",
            },
        )
        lie_plans = []
        for claim in claims:
            claim.setdefault("fact_refs", [])
            if claim.get("truthfulness") == "LIE":
                lie_plans.append(
                    {
                        "claim_id": claim["id"],
                        "purpose": "保护本人秘密或规避嫌疑",
                        "break_conditions": [],
                        "allowed_reactions": ["MAINTAIN", "NARROW", "REFUSE"],
                        "truth": claim.get("contradicts", ""),
                    }
                )
        suspect.setdefault("lie_plans", lie_plans)

    evidence = case.get("evidence", [])
    culprit_id = case.get("culprit_id")
    if evidence and not any("motive" in item.get("dimensions", []) for item in evidence):
        motive_candidate = next(
            (item for item in evidence if culprit_id in item.get("implicates", [])),
            evidence[0],
        )
        motive_candidate.setdefault("dimensions", []).append("motive")

    for item in evidence:
        discovery = item.get("discovery", {"type": "INITIAL"})
        kind = item.setdefault(
            "kind", _infer_evidence_kind(item.get("source", ""), item.get("title", ""))
        )
        action_type = item.setdefault("investigation_type", _investigation_type(kind))
        item.setdefault("action_label", _action_label(action_type))
        item.setdefault(
            "lead_description",
            f"有人提到“{item.get('title', '这项资料')}”可能存在，需要核对其原始来源。",
        )
        item.setdefault("related_topics", [discovery.get("topic", "evidence")])
        item.setdefault("supports_claim_ids", [])
        item.setdefault("contradicts_claim_ids", [])
        item.setdefault("related_subject_ids", item.get("implicates", []))
        item.setdefault("time_range", "")
        item["status"] = "已核验" if discovery.get("type") == "INITIAL" else "未核实"

    case.setdefault(
        "discovery_graph",
        [
            {
                "evidence_id": item["id"],
                "lead_trigger": item.get("discovery", {}),
                "verification_action": item.get("investigation_type"),
            }
            for item in evidence
        ],
    )
    proof = case["proof_rule"]
    required = set(proof.get("required_dimensions", []))
    required.update({"opportunity", "method", "motive"})
    proof["required_dimensions"] = sorted(required)
    return case


def validate_case(case: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "title", "setting", "victim", "location", "death_window",
        "summary", "culprit_id", "motive", "method", "truth_summary", "truth_timeline",
        "suspects", "evidence", "initial_evidence_ids", "proof_rule",
    }
    missing = required.difference(case)
    if missing:
        raise CaseValidationError(f"案件缺少字段: {', '.join(sorted(missing))}")

    suspects = case["suspects"]
    if not isinstance(suspects, list) or len(suspects) != 4:
        raise CaseValidationError("案件必须恰好包含 4 名嫌疑人")
    suspect_ids = [suspect.get("id") for suspect in suspects]
    if len(set(suspect_ids)) != 4 or any(not item for item in suspect_ids):
        raise CaseValidationError("嫌疑人 ID 必须存在且唯一")
    if case["culprit_id"] not in suspect_ids:
        raise CaseValidationError("真凶必须是嫌疑人之一")

    claim_ids: set[str] = set()
    for suspect in suspects:
        for field in ("name", "role", "initials", "public_bio", "personality", "secret"):
            if not suspect.get(field):
                raise CaseValidationError(f"嫌疑人 {suspect['id']} 缺少 {field}")
        claims = suspect.get("claims", [])
        topics = {claim.get("topic") for claim in claims}
        if not REQUIRED_TOPICS.issubset(topics):
            absent = REQUIRED_TOPICS.difference(topics)
            raise CaseValidationError(
                f"嫌疑人 {suspect['id']} 缺少话题: {', '.join(sorted(absent))}"
            )
        stances = {claim.get("truthfulness") for claim in claims}
        if "TRUTH" not in stances or "LIE" not in stances:
            raise CaseValidationError(f"嫌疑人 {suspect['id']} 必须同时拥有真话和谎言")
        for claim in claims:
            claim_id = claim.get("id")
            if not claim_id or claim_id in claim_ids:
                raise CaseValidationError("Claim ID 必须存在且全局唯一")
            claim_ids.add(claim_id)
            if claim.get("truthfulness") not in VALID_STANCES:
                raise CaseValidationError(f"Claim {claim_id} 的真实性类型无效")
            if not claim.get("content"):
                raise CaseValidationError(f"Claim {claim_id} 没有可展示内容")
            if claim.get("truthfulness") == "LIE" and not claim.get("contradicts"):
                raise CaseValidationError(f"谎言 {claim_id} 必须说明所冲突的事实")

    evidence = case["evidence"]
    if not isinstance(evidence, list) or len(evidence) < 5:
        raise CaseValidationError("案件至少需要 5 条证据")
    evidence_ids = [item.get("id") for item in evidence]
    if len(set(evidence_ids)) != len(evidence_ids) or any(not item for item in evidence_ids):
        raise CaseValidationError("Evidence ID 必须存在且唯一")
    evidence_id_set = set(evidence_ids)
    if not set(case["initial_evidence_ids"]).issubset(evidence_id_set):
        raise CaseValidationError("初始证据引用无效")

    suspect_by_id = {item["id"]: item for item in suspects}
    for item in evidence:
        for field in ("title", "description", "source", "dimensions", "discovery"):
            if not item.get(field):
                raise CaseValidationError(f"证据 {item['id']} 缺少 {field}")
        discovery = item["discovery"]
        if discovery.get("type") == "ASK":
            npc_id = discovery.get("npc_id")
            topic = discovery.get("topic")
            if npc_id not in suspect_by_id:
                raise CaseValidationError(f"证据 {item['id']} 的发现 NPC 无效")
            if topic not in {claim["topic"] for claim in suspect_by_id[npc_id]["claims"]}:
                raise CaseValidationError(f"证据 {item['id']} 的发现话题无效")
        elif discovery.get("type") != "INITIAL":
            raise CaseValidationError(f"证据 {item['id']} 的发现类型无效")

    proof_rule = case["proof_rule"]
    minimum = proof_rule.get("minimum_selected")
    if not isinstance(minimum, int) or not 2 <= minimum <= 4:
        raise CaseValidationError("证明规则的证据数量必须在 2–4 条之间")
    groups = proof_rule.get("any_of", [])
    if not groups:
        raise CaseValidationError("证明规则至少需要一组有效证据")
    for group in groups:
        if not set(group).issubset(evidence_id_set):
            raise CaseValidationError("证明规则引用了不存在的证据")
        if len(group) > 4:
            raise CaseValidationError("单组证明证据不能超过 4 条")

    case["public_timeline"] = case.get("public_timeline", [])
    case = _upgrade_case_v2(case)
    available_dimensions = {
        dimension for item in case["evidence"] for dimension in item.get("dimensions", [])
    }
    required_dimensions = set(case["proof_rule"].get("required_dimensions", []))
    if not required_dimensions.issubset(available_dimensions):
        raise CaseValidationError("必要证明维度无法由案件证据覆盖")
    return case


def freeze_case(case: dict[str, Any]) -> tuple[dict[str, Any], str]:
    normalized = json.loads(json.dumps(case, ensure_ascii=False, sort_keys=True))
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return normalized, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_initial_progress(case: dict[str, Any], action_limit: int) -> dict[str, Any]:
    evidence_states = {
        item["id"]: ("VERIFIED" if item["id"] in case["initial_evidence_ids"] else "UNVERIFIED")
        for item in case["evidence"]
    }
    return {
        "rules_version": "2.0",
        "action_limit": action_limit,
        "actions_remaining": action_limit,
        "question_limit": action_limit,
        "questions_remaining": action_limit,
        "discovered_evidence_ids": list(case["initial_evidence_ids"]),
        "evidence_states": evidence_states,
        "messages": [],
        "events": [],
        "npc_states": {
            suspect["id"]: {"pressure": 0, "state": "CALM"} for suspect in case["suspects"]
        },
        "processed_request_ids": {},
        "processed_action_ids": {},
        "accusation_request_ids": {},
        "review_used": False,
        "review_data": None,
    }


def upgrade_progress(case: dict[str, Any], progress: dict[str, Any]) -> dict[str, Any]:
    upgraded = clone(progress)
    was_v1 = upgraded.get("rules_version") != "2.0"
    limit = upgraded.get("action_limit", upgraded.get("question_limit", 18))
    remaining = upgraded.get("actions_remaining", upgraded.get("questions_remaining", limit))
    upgraded.update(
        {
            "rules_version": "2.0",
            "action_limit": limit,
            "actions_remaining": remaining,
            "question_limit": limit,
            "questions_remaining": remaining,
        }
    )
    discovered = upgraded.setdefault("discovered_evidence_ids", list(case["initial_evidence_ids"]))
    existing_states = upgraded.setdefault("evidence_states", {})
    for item in case["evidence"]:
        if item["id"] in discovered:
            existing_states.setdefault(item["id"], "VERIFIED" if was_v1 else "UNVERIFIED")
        else:
            existing_states.setdefault(item["id"], "UNVERIFIED")
    for evidence_id in case["initial_evidence_ids"]:
        existing_states[evidence_id] = "VERIFIED"
    upgraded.setdefault("events", [])
    upgraded.setdefault("processed_request_ids", {})
    upgraded.setdefault("processed_action_ids", {})
    upgraded.setdefault("accusation_request_ids", {})
    upgraded.setdefault("review_used", False)
    upgraded.setdefault("review_data", None)
    npc_states = upgraded.setdefault("npc_states", {})
    for suspect in case["suspects"]:
        npc_states.setdefault(suspect["id"], {"pressure": 0, "state": "CALM"})
    return upgraded


def _clock_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _extract_times(text: str) -> list[int]:
    results: list[int] = []
    for hour, minute in re.findall(r"(?<!\d)([01]?\d|2[0-3])[:：]([0-5]\d)", text):
        results.append(int(hour) * 60 + int(minute))
    pattern = re.compile(
        r"(凌晨|早上|上午|中午|下午|晚上)?\s*([0-9一二两三四五六七八九十]{1,3})\s*点(?:\s*([0-9一二两三四五六七八九十]{1,3})\s*分?)?"
    )
    numerals = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

    def chinese_number(value: str) -> int:
        if value.isdigit():
            return int(value)
        if value == "十":
            return 10
        if "十" in value:
            left, _, right = value.partition("十")
            return (numerals.get(left, 1) * 10) + numerals.get(right, 0)
        return numerals.get(value, 0)

    for period, raw_hour, raw_minute in pattern.findall(text):
        hour = chinese_number(raw_hour)
        minute = chinese_number(raw_minute) if raw_minute else 0
        if period in {"下午", "晚上"} and hour < 12:
            hour += 12
        if period == "中午" and hour < 11:
            hour += 12
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            value = hour * 60 + minute
            if value not in results:
                results.append(value)
    return results


def _time_range_from_question(question: str) -> dict[str, str] | None:
    times = _extract_times(question)
    if not times:
        return None
    approximate = any(item in question for item in ("左右", "前后", "大约", "差不多"))
    start = times[0] - (15 if approximate else 0)
    end = (times[1] if len(times) > 1 else times[0]) + (15 if approximate else 0)
    return {
        "start": _clock_label(max(0, start)),
        "end": _clock_label(min(1439, end)),
        "label": f"{_clock_label(times[0])}{' 左右' if approximate else ''}",
    }


def _understanding_label(intent: str, time_range: dict[str, str] | None) -> str:
    labels = {
        "ALIBI": "询问行踪",
        "LAST_SEEN": "询问最后见到死者的时间",
        "RELATIONSHIP": "询问与死者的关系",
        "MOTIVE": "询问冲突或动机",
        "METHOD": "询问作案手段或死因",
        "EVIDENCE": "询问证据与记录",
        "SECRET": "追问隐瞒事项",
        "WITNESS": "询问目击者或佐证人",
        "ACCOUNT": "质询账号与实际操作者",
        "PERMISSION": "质询权限",
        "GENERAL": "问题意图不明确",
    }
    label = labels[intent]
    if time_range:
        label += f" · {time_range['label']}"
    return label


def interpret_question(
    question: str,
    presented_evidence_ids: list[str],
    prior_messages: list[dict[str, Any]],
    referenced_claim_ids: list[str] | None = None,
) -> dict[str, Any]:
    normalized = re.sub(r"\s+", "", question.lower())
    intent = "GENERAL"
    for candidate, patterns in INTENT_PATTERNS:
        if any(pattern.replace(" ", "") in normalized for pattern in patterns):
            intent = candidate
            break
    if presented_evidence_ids and intent == "GENERAL":
        intent = "EVIDENCE"
    dialogue_act = "ASK"
    if any(item in normalized for item in ("不是说", "说过", "刚才", "矛盾", "不一致", "解释", "是不是", "确定")):
        dialogue_act = "CHALLENGE"
    elif presented_evidence_ids:
        dialogue_act = "PRESENT_EVIDENCE"

    references = list(referenced_claim_ids or [])
    if dialogue_act == "CHALLENGE" and not references:
        latest = next(
            (item for item in reversed(prior_messages) if item.get("claim_id_internal")),
            None,
        )
        if latest:
            references.append(latest["claim_id_internal"])

    time_range = _time_range_from_question(question)
    requested_slots = []
    if intent in {"ALIBI", "LAST_SEEN"}:
        requested_slots.extend(["time", "location"] if intent == "ALIBI" else ["time", "person"])
    if intent == "WITNESS":
        requested_slots.append("witness")
    if intent == "ACCOUNT":
        requested_slots.extend(["account_owner", "operator"])
    if intent == "PERMISSION":
        requested_slots.append("permission")
    confidence = 0.96 if intent != "GENERAL" else 0.38
    if presented_evidence_ids:
        confidence = max(confidence, 0.9)
    return {
        "dialogue_act": dialogue_act,
        "intent": intent,
        "topic": INTENT_TOPIC_MAP[intent],
        "time_range": time_range,
        "evidence_ids": presented_evidence_ids,
        "prior_claim_ids": references,
        "requested_slots": requested_slots,
        "confidence": confidence,
        "understanding": _understanding_label(intent, time_range),
    }


def classify_topic(question: str) -> str:
    return INTENT_TOPIC_MAP[interpret_question(question, [], [])["intent"]]


def clarification_options(suspect_name: str) -> list[str]:
    return [
        f"{suspect_name}，案发时间前后你在哪里？",
        f"{suspect_name}，你最后一次见到死者是什么时候？",
        f"{suspect_name}，谁能证明你的说法？",
    ]


def find_claim(suspect: dict[str, Any], topic: str) -> dict[str, Any]:
    claims = suspect["claims"]
    return next(
        (claim for claim in claims if claim["topic"] == topic),
        next(claim for claim in claims if claim["topic"] == "general"),
    )


def _claim_by_id(suspect: dict[str, Any], claim_id: str) -> dict[str, Any] | None:
    return next((claim for claim in suspect["claims"] if claim["id"] == claim_id), None)


def _claim_time_window(content: str) -> tuple[int, int] | None:
    times = _extract_times(content)
    if len(times) >= 2:
        return times[0], times[1]
    if len(times) == 1 and any(item in content for item in ("左右", "前后", "大约")):
        return max(0, times[0] - 15), min(1439, times[0] + 15)
    return None


def _evidence_specific_response(
    suspect: dict[str, Any],
    evidence: dict[str, Any],
    frame: dict[str, Any],
    base_claim: dict[str, Any],
) -> str:
    title = evidence["title"]
    description = evidence["description"]
    suspect_named = suspect["name"] in description or suspect["id"] in evidence.get("implicates", [])
    if frame["intent"] == "ACCOUNT":
        if suspect_named:
            return (
                f"你问的是“{title}”里的账号。账号确实与我有关；但一条登录记录只能证明账号被使用，"
                "要认定实际操作者，还需要把终端位置和当时行踪对上。"
            )
        return f"“{title}”没有直接写明是我的账号。你需要先说明哪一段记录指向我。"
    if frame["intent"] == "PERMISSION":
        return f"关于“{title}”涉及的权限，我的回答是：{find_claim(suspect, 'method')['content']}"
    if frame["dialogue_act"] == "CHALLENGE":
        return f"我知道你在用“{title}”质疑我。就这条记录本身，我的说法是：{base_claim['content']}"
    return f"我看过你出示的“{title}”。就它能证明的范围，我只能回答：{base_claim['content']}"


def suggested_followups(
    frame: dict[str, Any], presented: list[dict[str, Any]]
) -> list[str]:
    suggestions: list[str]
    if frame["intent"] == "ALIBI":
        suggestions = ["谁能证明你的行踪？", "你最后一次见到死者是什么时候？"]
    elif frame["intent"] in {"ACCOUNT", "PERMISSION", "EVIDENCE"}:
        suggestions = ["这条记录中的时间你怎么解释？", "当时还有谁能接触这个系统？"]
    elif frame["intent"] == "LAST_SEEN":
        suggestions = ["当时死者身边还有谁？", "你们谈了什么？"]
    else:
        suggestions = ["案发时间前后你在哪里？", "谁能证明你的说法？"]
    if presented:
        suggestions.insert(0, f"“{presented[0]['title']}”与你刚才的说法不一致，你怎么解释？")
    return suggestions[:3]


def build_answer_plan(
    case: dict[str, Any],
    suspect: dict[str, Any],
    frame: dict[str, Any],
    progress: dict[str, Any],
) -> dict[str, Any]:
    topic = frame["topic"]
    claim = find_claim(suspect, topic)
    evidence_by_id = {item["id"]: item for item in case["evidence"]}
    presented = [evidence_by_id[item] for item in frame["evidence_ids"] if item in evidence_by_id]
    prior_claim = next(
        (
            _claim_by_id(suspect, claim_id)
            for claim_id in frame["prior_claim_ids"]
            if _claim_by_id(suspect, claim_id)
        ),
        None,
    )

    draft = claim["content"]
    coverage = "DIRECT"
    strategy = claim["truthfulness"]
    if frame["intent"] == "ALIBI" and frame.get("time_range"):
        requested_start = _extract_times(frame["time_range"]["start"])[0]
        requested_end = _extract_times(frame["time_range"]["end"])[0]
        claim_window = _claim_time_window(claim["content"])
        if claim_window and not (claim_window[0] <= requested_end and requested_start <= claim_window[1]):
            draft = (
                f"你问的是 {frame['time_range']['label']}。我刚才这段可核对的行程只覆盖 "
                f"{_clock_label(claim_window[0])}–{_clock_label(claim_window[1])}；"
                "它不能证明你所问的那个时间点。那个时间我没有可以当场交给你核对的记录。"
            )
            coverage = "PARTIAL"
            strategy = "UNKNOWN"
    elif frame["intent"] == "WITNESS":
        alibi = find_claim(suspect, "alibi")
        witness_markers = ("作证", "快递员", "摄像头", "记录", "工单", "门禁", "操作记录")
        if any(marker in alibi["content"] for marker in witness_markers):
            draft = f"你问谁能佐证我的行踪：{alibi['content']}"
        else:
            draft = "没有人能直接替我作证。我能提供的只有可核对的时间和记录，不能把它说成目击证词。"
        claim = alibi
    elif frame["intent"] in {"ACCOUNT", "PERMISSION"} and not presented:
        related = next(
            (
                item for item in case["evidence"]
                if item["id"] in progress.get("discovered_evidence_ids", [])
                and (suspect["name"] in item["description"] or suspect["id"] in item.get("implicates", []))
            ),
            None,
        )
        if related:
            draft = _evidence_specific_response(suspect, related, frame, claim)
        else:
            draft = f"你问的是账号或权限。我能确认的是：{claim['content']}"
    if presented:
        draft = _evidence_specific_response(suspect, presented[0], frame, claim)
    elif prior_claim:
        draft = f"你指的是我刚才那句“{prior_claim['content']}”。我的说法没有变：{claim['content']}"

    npc_state = progress.get("npc_states", {}).get(suspect["id"], {"pressure": 0})
    pressure_delta = 1 if (presented or frame["dialogue_act"] == "CHALLENGE") else 0
    next_pressure = min(3, int(npc_state.get("pressure", 0)) + pressure_delta)
    return {
        "coverage": coverage,
        "strategy": strategy,
        "topic": topic,
        "intent": frame["intent"],
        "claim_id": claim["id"],
        "authorized_claim_ids": [claim["id"]] + ([prior_claim["id"]] if prior_claim else []),
        "draft": draft,
        "reaction": PRESSURE_STATES[next_pressure],
        "pressure": next_pressure,
        "must_address": frame["requested_slots"],
        "suggested_followups": suggested_followups(frame, presented),
    }


def discover_evidence(
    case: dict[str, Any], npc_id: str, topic: str, already_discovered: list[str]
) -> list[str]:
    existing = set(already_discovered)
    return [
        evidence["id"]
        for evidence in case["evidence"]
        if evidence["id"] not in existing
        and evidence["discovery"].get("type") == "ASK"
        and evidence["discovery"].get("npc_id") == npc_id
        and evidence["discovery"].get("topic") == topic
    ]


def public_evidence(
    case: dict[str, Any],
    evidence_ids: list[str],
    evidence_states: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    wanted = set(evidence_ids)
    states = evidence_states or {
        item["id"]: "VERIFIED" for item in case["evidence"] if item["id"] in wanted
    }
    result = []
    for item in case["evidence"]:
        if item["id"] not in wanted:
            continue
        state = states.get(item["id"], "UNVERIFIED")
        verified = state in {"VERIFIED", "CONTESTED"}
        result.append(
            {
                "id": item["id"],
                "title": item["title"],
                "description": item["description"] if verified else item.get("lead_description", "来源尚未核实。"),
                "source": item["source"] if verified else "待调取来源",
                "status": EVIDENCE_STATE_LABELS.get(state, state),
                "verification_state": state,
                "kind": item.get("kind", "PHYSICAL_EVIDENCE"),
                "dimensions": item.get("dimensions", []) if verified else [],
                "related_subject_ids": item.get("related_subject_ids", []),
                "action_type": item.get("investigation_type"),
                "action_label": item.get("action_label", "核验来源"),
                "usable_in_accusation": state == "VERIFIED",
            }
        )
    return result


def public_dialogue(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry["id"],
        "npc_id": entry["npc_id"],
        "question": entry["question"],
        "response": entry["response"],
        "topic": entry.get("topic", "general"),
        "intent": entry.get("intent", entry.get("topic", "general").upper()),
        "understanding": entry.get("understanding", ""),
        "coverage": entry.get("coverage", "DIRECT"),
        "reaction": entry.get("reaction", "CALM"),
        "consumed_action": entry.get("consumed_action", True),
        "referenced_claim_ids": entry.get("referenced_claim_ids", []),
        "suggested_followups": entry.get("suggested_followups", []),
        "discovered_evidence_ids": entry.get("discovered_evidence_ids", []),
        "created_at": entry["created_at"],
    }


def build_notebook(case: dict[str, Any], progress: dict[str, Any]) -> dict[str, Any]:
    messages = progress.get("messages", [])
    states = progress.get("evidence_states", {})
    discovered_ids = progress.get("discovered_evidence_ids", [])
    evidence_by_id = {item["id"]: item for item in case["evidence"]}
    contradictions: list[dict[str, str]] = []
    caught_claim_ids: set[str] = set()
    for message in messages:
        if message.get("stance_internal") != "LIE":
            continue
        npc_id = message["npc_id"]
        related = next(
            (
                evidence_by_id[evidence_id]
                for evidence_id in discovered_ids
                if states.get(evidence_id) == "VERIFIED"
                and evidence_id in evidence_by_id
                and "contradiction" in evidence_by_id[evidence_id].get("dimensions", [])
                and npc_id in evidence_by_id[evidence_id].get("implicates", [])
            ),
            None,
        )
        if related:
            contradictions.append(
                {
                    "id": f"contradiction-{message['id']}",
                    "npc_id": npc_id,
                    "claim": message["response"],
                    "evidence_id": related["id"],
                    "label": f"该口供可能与“{related['title']}”冲突",
                }
            )
            caught_claim_ids.add(message.get("claim_id_internal", ""))

    summaries = []
    for suspect in case["suspects"]:
        npc_messages = [item for item in messages if item["npc_id"] == suspect["id"]]
        unverified = sum(
            1 for evidence_id in discovered_ids
            if states.get(evidence_id) == "UNVERIFIED"
            and suspect["id"] in evidence_by_id.get(evidence_id, {}).get("related_subject_ids", [])
        )
        summaries.append(
            {
                "npc_id": suspect["id"],
                "interview_count": len(npc_messages),
                "unverified_count": unverified,
                "contradiction_count": sum(1 for item in contradictions if item["npc_id"] == suspect["id"]),
                "pressure_state": progress.get("npc_states", {}).get(suspect["id"], {}).get("state", "CALM"),
            }
        )

    timeline_entries = list(case.get("public_timeline", []))
    for message in messages:
        if message.get("intent") in {"ALIBI", "LAST_SEEN"}:
            times = _extract_times(message["response"])
            if times:
                suspect = next(item for item in case["suspects"] if item["id"] == message["npc_id"])
                timeline_entries.append(
                    {
                        "time": _clock_label(times[0]),
                        "event": f"{suspect['name']} 口供：{message['response']}",
                        "status": "TESTIMONY",
                    }
                )
    return {
        "suspect_summaries": summaries,
        "contradictions": contradictions,
        "timeline_entries": timeline_entries,
        "caught_claim_ids": sorted(item for item in caught_claim_ids if item),
    }


def public_state(
    case_id: str,
    status: str,
    case: dict[str, Any],
    progress: dict[str, Any],
    generation_source: str,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    notebook = build_notebook(case, progress)
    summaries = {item["npc_id"]: item for item in notebook["suspect_summaries"]}
    action_limit = progress.get("action_limit", progress.get("question_limit", 18))
    actions_remaining = progress.get("actions_remaining", progress.get("questions_remaining", 18))
    return {
        "case_id": case_id,
        "schema_version": case.get("schema_version", "2.0"),
        "status": status,
        "brief": {
            "title": case["title"], "setting": case["setting"], "victim": case["victim"],
            "location": case["location"], "death_window": case["death_window"],
            "summary": case["summary"], "public_timeline": case.get("public_timeline", []),
        },
        "suspects": [
            {
                "id": suspect["id"], "name": suspect["name"], "role": suspect["role"],
                "initials": suspect["initials"], "public_bio": suspect["public_bio"],
                "personality": suspect["personality"], **summaries.get(suspect["id"], {}),
            }
            for suspect in case["suspects"]
        ],
        "evidence": public_evidence(case, progress["discovered_evidence_ids"], progress.get("evidence_states", {})),
        "messages": [public_dialogue(entry) for entry in progress["messages"]],
        "action_limit": action_limit,
        "actions_remaining": actions_remaining,
        "question_limit": action_limit,
        "questions_remaining": actions_remaining,
        "review_used": progress.get("review_used", False),
        "review": progress.get("review_data"),
        "notebook": notebook,
        "generation_source": generation_source,
        "result": result,
    }


def evaluate_accusation(
    case: dict[str, Any],
    suspect_id: str,
    selected_evidence_ids: list[str],
    theory: dict[str, list[str]] | None = None,
) -> tuple[str, list[str]]:
    selected = set(selected_evidence_ids)
    proof = case["proof_rule"]
    evidence_by_id = {item["id"]: item for item in case["evidence"]}
    selected_dimensions = {
        dimension
        for evidence_id in selected
        if evidence_id in evidence_by_id
        for dimension in evidence_by_id[evidence_id].get("dimensions", [])
    }
    required_dimensions = set(proof.get("required_dimensions", [])) | {"opportunity", "method", "motive"}
    missing = set(required_dimensions.difference(selected_dimensions))
    if theory:
        for dimension in ("motive", "method", "opportunity"):
            mapped = theory.get(dimension, [])
            if not mapped or not any(
                dimension in evidence_by_id.get(item, {}).get("dimensions", []) for item in mapped
            ):
                missing.add(dimension)
    matching_group = any(set(group).issubset(selected) for group in proof["any_of"])
    evidence_sufficient = len(selected) >= proof["minimum_selected"] and not missing and matching_group
    if suspect_id != case["culprit_id"]:
        return "WRONG", sorted(missing)
    if evidence_sufficient:
        return "SOLVED", []
    return "INSUFFICIENT", sorted(missing)


def review_accusation(
    case: dict[str, Any], selected_evidence_ids: list[str], theory: dict[str, list[str]]
) -> dict[str, Any]:
    evidence_by_id = {item["id"]: item for item in case["evidence"]}
    coverage: dict[str, bool] = {}
    feedback: list[str] = []
    for dimension in ("motive", "method", "opportunity"):
        mapped = theory.get(dimension, [])
        covered = bool(mapped) and any(
            dimension in evidence_by_id.get(item, {}).get("dimensions", []) for item in mapped
        )
        coverage[dimension] = covered
        if not covered:
            feedback.append(f"{DIMENSION_LABELS[dimension]}仍缺少能够直接支撑该判断的已核验证据。")
    if all(coverage.values()) and not any(
        set(group).issubset(set(selected_evidence_ids)) for group in case["proof_rule"]["any_of"]
    ):
        feedback.append("三项条件都有材料，但它们之间还没有形成同一条完整、相互独立的证明链。")
    if not feedback:
        feedback.append("动机、手段和机会均已有支撑。最终提交前请确认这些证据来自相互独立的来源。")
    return {"coverage": coverage, "feedback": feedback, "used": True}


def build_result(
    case: dict[str, Any],
    outcome: str,
    selected_evidence_ids: list[str],
    missing_dimensions: list[str],
    progress: dict[str, Any] | None = None,
    theory: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    culprit = next(item for item in case["suspects"] if item["id"] == case["culprit_id"])
    if outcome == "SOLVED":
        headline = "指控成立，案件告破"
        explanation = "你锁定了真正的凶手，也用动机、手段与机会闭合了证据链。"
    elif outcome == "INSUFFICIENT":
        headline = "方向正确，但证据链不足"
        explanation = "你找对了凶手，但提交的材料还没有完整证明动机、手段与作案机会。"
    else:
        headline = "指控错误"
        explanation = "现有事实无法支持你的指控。下面将把你的调查与封存真相逐项对照。"

    source_progress = progress or build_initial_progress(case, 18)
    heard_claim_ids = {item.get("claim_id_internal", "") for item in source_progress.get("messages", [])}
    caught_claim_ids = set(build_notebook(case, source_progress)["caught_claim_ids"])
    key_lies = []
    for suspect in case["suspects"]:
        for claim in suspect["claims"]:
            if claim["truthfulness"] != "LIE":
                continue
            discovery_status = (
                "CAUGHT" if claim["id"] in caught_claim_ids
                else "HEARD" if claim["id"] in heard_claim_ids else "MISSED"
            )
            key_lies.append(
                {
                    "claim_id": claim["id"], "speaker": suspect["name"],
                    "claim": claim["content"], "truth": claim["contradicts"],
                    "discovery_status": discovery_status,
                }
            )

    evidence_by_id = {item["id"]: item for item in case["evidence"]}
    evidence_analysis = [
        {
            "evidence_id": evidence_id,
            "title": evidence_by_id[evidence_id]["title"],
            "dimensions": evidence_by_id[evidence_id].get("dimensions", []),
            "mapped_to": [dimension for dimension, ids in (theory or {}).items() if evidence_id in ids],
        }
        for evidence_id in selected_evidence_ids if evidence_id in evidence_by_id
    ]
    return {
        "outcome": outcome,
        "headline": headline,
        "explanation": explanation,
        "culprit_id": culprit["id"],
        "culprit_name": culprit["name"],
        "motive": case["motive"],
        "method": case["method"],
        "truth_summary": case["truth_summary"],
        "truth_timeline": case["truth_timeline"],
        "key_lies": key_lies,
        "selected_evidence_ids": selected_evidence_ids,
        "evidence_analysis": evidence_analysis,
        "player_theory": theory or {},
        "missing_dimensions": [DIMENSION_LABELS.get(item, item) for item in missing_dimensions],
    }


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def clone(value: Any) -> Any:
    return copy.deepcopy(value)
