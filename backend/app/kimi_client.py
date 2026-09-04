from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .config import Settings


CASE_SYSTEM_PROMPT = """你是推理游戏的案件架构师。你只输出合法 JSON 对象，不使用 Markdown。
你生成的是虚构、克制、非血腥的封闭案件。案件必须唯一可解，所有事实在开局后永久冻结。
四名嫌疑人必须各自同时拥有真话与预设谎言；谎言只能描述错误版本，并明确对应的真实冲突。
不得使用现实人物或现实机构，不得把受保护属性设为作案动机。"""


CASE_USER_PROMPT = """根据随机种子 {seed}，生成一个中文现代科研机构背景的全新案件。

严格满足以下 JSON 契约：
{{
  "schema_version": "2.0",
  "title": "案件标题",
  "setting": "虚构机构",
  "victim": {{"name": "虚构成年人姓名", "role": "身份"}},
  "location": "案发地点",
  "death_window": "HH:MM–HH:MM",
  "summary": "只含开局公开信息，不泄露真凶",
  "public_timeline": [{{"time":"时间", "event":"公开事件"}}],
  "culprit_id": "alice|bob|charlie|david 中的一个",
  "motive": "真实动机",
  "method": "真实手段，避免可操作的危险细节",
  "truth_summary": "完整真相",
  "truth_timeline": [{{"time":"时间", "event":"真实事件"}}],
  "suspects": [
    {{
      "id": "alice",
      "name": "姓名",
      "role": "身份",
      "initials": "两字简称",
      "public_bio": "公开介绍",
      "personality": "说话风格",
      "secret": "隐藏秘密，可与凶案无关",
      "claims": [
        {{"id":"alice_alibi", "topic":"alibi", "truthfulness":"TRUTH|LIE|EVASIVE|UNKNOWN", "content":"可直接对玩家说的一到两句话", "contradicts":"若为 LIE，写被其冲突的真实事实，否则空字符串"}}
      ]
    }}
  ],
  "evidence": [
    {{
      "id":"ev_unique_id",
      "title":"证据名",
      "description":"玩家发现后可见的客观描述",
      "source":"来源",
      "status":"已验证",
      "dimensions":["opportunity|method|motive|contradiction"],
      "implicates":["alice|bob|charlie|david"],
      "discovery":{{"type":"INITIAL"}}
    }},
    {{
      "id":"ev_unique_id_2",
      "title":"证据名",
      "description":"描述",
      "source":"来源",
      "status":"已验证",
      "dimensions":["opportunity"],
      "implicates":["bob"],
      "discovery":{{"type":"ASK", "npc_id":"alice", "topic":"evidence"}}
    }}
  ],
  "initial_evidence_ids":["某个 INITIAL 证据 ID"],
  "proof_rule":{{
    "minimum_selected":3,
    "required_dimensions":["opportunity","method"],
    "any_of":[["三条足以闭合证据链的 ID"]]
  }}
}}

硬性要求：
1. suspects 恰好四项，id 依次且只能为 alice、bob、charlie、david。
2. 每名嫌疑人必须恰好包含八个 topic：alibi、relationship、last_seen、motive、method、evidence、secret、general；每个 topic 一条 claim，claim id 全局唯一。
3. 每名嫌疑人至少一条 TRUTH 和一条 LIE。每条 LIE 的 contradicts 不能为空。general 应为 UNKNOWN。
4. evidence 为 5–7 条，至少一条 INITIAL，其余 ASK 的 npc_id 和 topic 必须能命中对应嫌疑人的 claim。
5. 仅凭可发现证据存在唯一真凶。proof_rule 的每组含 2–4 条证据，至少包含机会和手段两个维度。
6. 真凶必须在死亡窗口具备动机、手段和机会；非真凶不得拥有同等充分证据链。
7. 所有人物、机构均为虚构。输出只能是一个 JSON 对象。"""


class KimiClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def available(self) -> bool:
        return self.settings.kimi_enabled and bool(self.settings.kimi_api_key)

    async def _chat_json(
        self,
        messages: list[dict[str, str]],
        max_completion_tokens: int,
        *,
        prompt_cache_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("Kimi API 未配置")

        payload: dict[str, Any] = {
            "model": self.settings.kimi_model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": max_completion_tokens,
            "reasoning_effort": self.settings.kimi_reasoning_effort,
        }
        if prompt_cache_key:
            payload["prompt_cache_key"] = prompt_cache_key

        headers = {
            "Authorization": f"Bearer {self.settings.kimi_api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.settings.kimi_base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(
            timeout=timeout_seconds or self.settings.kimi_timeout_seconds
        ) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            if response.status_code == 400 and "reasoning_effort" in payload:
                payload.pop("reasoning_effort", None)
                response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()

        body = response.json()
        content = body["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise RuntimeError("Kimi 返回的不是 JSON 对象")
        return parsed

    async def generate_case(self, seed: str) -> dict[str, Any]:
        result = await self._chat_json(
            [
                {"role": "system", "content": CASE_SYSTEM_PROMPT},
                {"role": "user", "content": CASE_USER_PROMPT.format(seed=seed)},
            ],
            max_completion_tokens=10000,
            prompt_cache_key=f"case-generator-v2-{seed[:8]}",
        )
        if "case" in result and isinstance(result["case"], dict):
            return result["case"]
        return result

    async def choose_topic(
        self, question: str, npc_id: str, case_id: str
    ) -> str | None:
        if not self.available:
            return None
        result = await self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是推理游戏的问题路由器。只判断玩家问题最接近哪个话题，"
                        "绝不回答问题。输出 JSON：{\"topic\":\"...\"}。可选值只有 "
                        "alibi, relationship, last_seen, motive, method, evidence, secret, general。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"当前 NPC={npc_id}。玩家问题：{question}",
                },
            ],
            max_completion_tokens=120,
            prompt_cache_key=f"{case_id}-{npc_id}",
        )
        topic = result.get("topic")
        return topic if topic in {
            "alibi",
            "relationship",
            "last_seen",
            "motive",
            "method",
            "evidence",
            "secret",
            "general",
        } else None

    async def realize_dialogue(
        self,
        *,
        case_id: str,
        npc_name: str,
        personality: str,
        player_question: str,
        grounded_draft: str,
        authorized_claim_ids: list[str],
    ) -> dict[str, Any] | None:
        """Rewrite a grounded answer without granting the model authority over facts."""
        if not self.available or not self.settings.kimi_dialogue_enabled:
            return None
        result = await self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是推理游戏 NPC 的语言表达器，不是案件作者。"
                        "事实已经由服务器决定。只能改写给定的 grounded_draft，"
                        "不得新增或删除人物、时间、地点、账号、权限、证据结论与事实断言。"
                        "先正面回应玩家所问内容，保持人物口吻，最多三句。"
                        "输出 JSON：{\"response_text\":\"...\",\"assertion_ids\":[\"...\"]}。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"NPC：{npc_name}\n"
                        f"人物风格：{personality}\n"
                        f"玩家问题：{player_question}\n"
                        f"grounded_draft：{grounded_draft}\n"
                        f"允许断言 ID：{json.dumps(authorized_claim_ids, ensure_ascii=False)}"
                    ),
                },
            ],
            max_completion_tokens=420,
            prompt_cache_key=f"dialogue-v2-{case_id[:8]}-{npc_name}",
            timeout_seconds=self.settings.kimi_dialogue_timeout_seconds,
        )
        response_text = result.get("response_text")
        assertion_ids = result.get("assertion_ids", [])
        if not isinstance(response_text, str) or not response_text.strip():
            return None
        if not isinstance(assertion_ids, list) or not set(assertion_ids).issubset(
            set(authorized_claim_ids)
        ):
            return None
        if len(response_text) > 320:
            return None
        # A rewrite may not introduce new clock times absent from the grounded draft.
        time_pattern = r"(?<!\d)(?:[01]?\d|2[0-3])[:：][0-5]\d"
        allowed_times = set(re.findall(time_pattern, grounded_draft))
        produced_times = set(re.findall(time_pattern, response_text))
        if not produced_times.issubset(allowed_times):
            return None
        return {"response_text": response_text.strip(), "assertion_ids": assertion_ids}
