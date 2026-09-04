from __future__ import annotations

import logging
import secrets
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .case_engine import (
    build_answer_plan,
    build_initial_progress,
    build_notebook,
    build_result,
    clarification_options,
    clone,
    discover_evidence,
    evaluate_accusation,
    freeze_case,
    interpret_question,
    public_dialogue,
    public_evidence,
    public_state,
    review_accusation,
    upgrade_progress,
    utc_now_iso,
    validate_case,
)
from .case_templates import build_fallback_case
from .config import Settings
from .kimi_client import KimiClient
from .models import GameSession
from .schemas import (
    AccusationRequest,
    AccusationReviewRequest,
    InterrogationRequest,
    InvestigationRequest,
)


logger = logging.getLogger(__name__)
PLAYABLE_STATUSES = {"ACTIVE", "REVIEWED"}


class GameService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.kimi = KimiClient(settings)

    async def create_game(self, db: Session) -> dict[str, Any]:
        case_id = str(uuid.uuid4())
        seed = secrets.token_hex(16)
        generation_source = "fallback"
        generation_error: str | None = None
        case: dict[str, Any] | None = None

        if self.kimi.available:
            try:
                candidate = await self.kimi.generate_case(seed)
                case = validate_case(candidate)
                generation_source = "kimi"
            except Exception as exc:  # External model failures must not block play.
                generation_error = f"{type(exc).__name__}: {str(exc)[:700]}"
                logger.warning("Kimi case generation failed: %s", exc)
        if case is None:
            case = validate_case(build_fallback_case(seed))

        frozen_case, content_hash = freeze_case(case)
        progress = build_initial_progress(frozen_case, self.settings.question_limit)
        session = GameSession(
            id=case_id,
            status="ACTIVE",
            schema_version=frozen_case["schema_version"],
            content_hash=content_hash,
            generation_source=generation_source,
            case_data=frozen_case,
            progress_data=progress,
            result_data=None,
            last_error=generation_error,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return self._public(session)

    def get_game(self, db: Session, case_id: str) -> dict[str, Any]:
        session = self._get_session(db, case_id)
        self._ensure_v2(db, session)
        return self._public(session)

    async def interrogate(
        self, db: Session, case_id: str, request: InterrogationRequest
    ) -> dict[str, Any]:
        session = self._get_session(db, case_id)
        self._ensure_v2(db, session)
        progress = clone(session.progress_data)

        processed = progress.get("processed_request_ids", {})
        if request.request_id in processed:
            return processed[request.request_id]["response"]
        self._require_playable(session)
        if progress["actions_remaining"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="调查额度已用完，请整理证据并提交指控",
            )

        suspects = {item["id"]: item for item in session.case_data["suspects"]}
        suspect = suspects.get(request.npc_id)
        if not suspect:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="嫌疑人不存在")

        discovered = set(progress["discovered_evidence_ids"])
        unknown_evidence = set(request.presented_evidence_ids).difference(discovered)
        if unknown_evidence:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能出示尚未发现的资料")
        unverified = [
            evidence_id
            for evidence_id in request.presented_evidence_ids
            if progress["evidence_states"].get(evidence_id) != "VERIFIED"
        ]
        if unverified:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="线索核验后才能作为证据出示")

        npc_messages = [
            item for item in progress["messages"] if item["npc_id"] == suspect["id"]
        ]
        parser_question = request.question
        if request.context_time and request.context_time not in parser_question:
            parser_question = f"{parser_question}（时间：{request.context_time}）"
        frame = interpret_question(
            parser_question,
            request.presented_evidence_ids,
            npc_messages,
            request.referenced_claim_ids,
        )
        if frame["confidence"] < 0.7:
            response = {
                "status": "NEEDS_CLARIFICATION",
                "entry": None,
                "new_evidence": [],
                "clarification_options": clarification_options(suspect["name"]),
                "understanding": frame["understanding"],
                "consumed_action": False,
                "actions_remaining": progress["actions_remaining"],
                "questions_remaining": progress["actions_remaining"],
                "notebook": build_notebook(session.case_data, progress),
            }
            processed[request.request_id] = {"response": response}
            progress["processed_request_ids"] = processed
            session.progress_data = progress
            session.version += 1
            db.commit()
            return response

        plan = build_answer_plan(session.case_data, suspect, frame, progress)
        response_text = plan["draft"]
        if self.kimi.available and self.settings.kimi_dialogue_enabled:
            try:
                realized = await self.kimi.realize_dialogue(
                    case_id=case_id,
                    npc_name=suspect["name"],
                    personality=suspect["personality"],
                    player_question=request.question,
                    grounded_draft=plan["draft"],
                    authorized_claim_ids=plan["authorized_claim_ids"],
                )
                if realized:
                    response_text = realized["response_text"]
            except Exception as exc:
                logger.info("Kimi dialogue realization fallback: %s", exc)

        new_evidence_ids = discover_evidence(
            session.case_data,
            suspect["id"],
            plan["topic"],
            progress["discovered_evidence_ids"],
        )
        progress["discovered_evidence_ids"].extend(new_evidence_ids)
        for evidence_id in new_evidence_ids:
            progress["evidence_states"][evidence_id] = "UNVERIFIED"

        progress["actions_remaining"] -= 1
        progress["questions_remaining"] = progress["actions_remaining"]
        progress["npc_states"][suspect["id"]] = {
            "pressure": plan["pressure"],
            "state": plan["reaction"],
        }
        entry = {
            "id": str(uuid.uuid4()),
            "npc_id": suspect["id"],
            "question": request.question,
            "response": response_text,
            "topic": plan["topic"],
            "intent": plan["intent"],
            "understanding": frame["understanding"],
            "coverage": plan["coverage"],
            "reaction": plan["reaction"],
            "consumed_action": True,
            "claim_id_internal": plan["claim_id"],
            "stance_internal": plan["strategy"],
            "referenced_claim_ids": frame["prior_claim_ids"],
            "suggested_followups": plan["suggested_followups"],
            "discovered_evidence_ids": new_evidence_ids,
            "created_at": utc_now_iso(),
        }
        progress["messages"].append(entry)
        progress["events"].append(
            {
                "id": str(uuid.uuid4()),
                "type": "INTERROGATION",
                "npc_id": suspect["id"],
                "entry_id": entry["id"],
                "consumed": 1,
                "created_at": entry["created_at"],
            }
        )
        response = {
            "status": "ANSWERED",
            "entry": public_dialogue(entry),
            "new_evidence": public_evidence(
                session.case_data, new_evidence_ids, progress["evidence_states"]
            ),
            "clarification_options": [],
            "understanding": frame["understanding"],
            "consumed_action": True,
            "actions_remaining": progress["actions_remaining"],
            "questions_remaining": progress["actions_remaining"],
            "notebook": build_notebook(session.case_data, progress),
        }
        processed[request.request_id] = {"response": response}
        progress["processed_request_ids"] = processed
        session.progress_data = progress
        session.version += 1
        db.commit()
        return response

    def investigate(
        self, db: Session, case_id: str, request: InvestigationRequest
    ) -> dict[str, Any]:
        session = self._get_session(db, case_id)
        self._ensure_v2(db, session)
        self._require_playable(session)
        progress = clone(session.progress_data)
        processed = progress.get("processed_action_ids", {})
        if request.request_id in processed:
            return processed[request.request_id]["response"]
        if progress["actions_remaining"] <= 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="调查额度已用完")
        if request.evidence_id not in progress["discovered_evidence_ids"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="线索尚未发现")
        evidence = next(
            (item for item in session.case_data["evidence"] if item["id"] == request.evidence_id),
            None,
        )
        if not evidence:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料不存在")
        current_state = progress["evidence_states"].get(request.evidence_id, "UNVERIFIED")
        if current_state == "VERIFIED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该资料已经核验")
        if request.action_type != evidence.get("investigation_type"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="核验方式与资料来源不匹配")

        progress["evidence_states"][request.evidence_id] = "VERIFIED"
        progress["actions_remaining"] -= 1
        progress["questions_remaining"] = progress["actions_remaining"]
        progress["events"].append(
            {
                "id": str(uuid.uuid4()),
                "type": request.action_type,
                "evidence_id": request.evidence_id,
                "consumed": 1,
                "created_at": utc_now_iso(),
            }
        )
        public_item = public_evidence(
            session.case_data, [request.evidence_id], progress["evidence_states"]
        )[0]
        response = {
            "evidence": public_item,
            "actions_remaining": progress["actions_remaining"],
            "questions_remaining": progress["actions_remaining"],
            "notebook": build_notebook(session.case_data, progress),
        }
        processed[request.request_id] = {"response": response}
        progress["processed_action_ids"] = processed
        session.progress_data = progress
        session.version += 1
        db.commit()
        return response

    def review(
        self, db: Session, case_id: str, request: AccusationReviewRequest
    ) -> dict[str, Any]:
        session = self._get_session(db, case_id)
        self._ensure_v2(db, session)
        self._require_playable(session)
        progress = clone(session.progress_data)
        if progress.get("review_used"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="本局检方预审已经使用")
        self._validate_suspect(session, request.suspect_id)
        selected = request.theory.all_evidence_ids()
        self._require_verified_evidence(session, progress, selected)
        review = review_accusation(session.case_data, selected, request.theory.model_dump())
        progress["review_used"] = True
        progress["review_data"] = review
        progress["events"].append(
            {"id": str(uuid.uuid4()), "type": "ACCUSATION_REVIEW", "created_at": utc_now_iso()}
        )
        session.progress_data = progress
        session.status = "REVIEWED"
        session.version += 1
        db.commit()
        return review

    def accuse(
        self, db: Session, case_id: str, request: AccusationRequest
    ) -> dict[str, Any]:
        session = self._get_session(db, case_id)
        self._ensure_v2(db, session)
        progress = clone(session.progress_data)
        accusation_ids = progress.get("accusation_request_ids", {})
        if request.request_id in accusation_ids and session.result_data:
            return session.result_data
        self._require_playable(session)
        self._validate_suspect(session, request.suspect_id)

        selected = request.selected_evidence_ids()
        if len(selected) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少提交两条已核验证据")
        self._require_verified_evidence(session, progress, selected)
        theory = request.theory.model_dump() if request.theory else None
        outcome, missing = evaluate_accusation(
            session.case_data, request.suspect_id, selected, theory
        )
        result = build_result(
            session.case_data, outcome, selected, missing, progress, theory
        )
        session.status = "SOLVED" if outcome == "SOLVED" else "FAILED"
        session.result_data = result
        accusation_ids[request.request_id] = True
        progress["accusation_request_ids"] = accusation_ids
        progress["events"].append(
            {"id": str(uuid.uuid4()), "type": "FINAL_ACCUSATION", "outcome": outcome, "created_at": utc_now_iso()}
        )
        session.progress_data = progress
        session.version += 1
        db.commit()
        return result

    def _ensure_v2(self, db: Session, session: GameSession) -> None:
        needs_case_upgrade = session.schema_version != "2.0" or not session.case_data.get("engine_version")
        if needs_case_upgrade:
            upgraded_case = validate_case(clone(session.case_data))
            frozen_case, content_hash = freeze_case(upgraded_case)
            session.case_data = frozen_case
            session.schema_version = "2.0"
            session.content_hash = content_hash
        upgraded_progress = upgrade_progress(session.case_data, session.progress_data)
        if needs_case_upgrade or upgraded_progress != session.progress_data:
            session.progress_data = upgraded_progress
            session.version += 1
            db.commit()

    @staticmethod
    def _require_playable(session: GameSession) -> None:
        if session.status not in PLAYABLE_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="案件已经结案")

    @staticmethod
    def _validate_suspect(session: GameSession, suspect_id: str) -> None:
        if suspect_id not in {item["id"] for item in session.case_data["suspects"]}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="嫌疑人不存在")

    @staticmethod
    def _require_verified_evidence(
        session: GameSession, progress: dict[str, Any], evidence_ids: list[str]
    ) -> None:
        discovered = set(progress["discovered_evidence_ids"])
        if not set(evidence_ids).issubset(discovered):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="包含尚未发现的资料")
        if any(progress["evidence_states"].get(item) != "VERIFIED" for item in evidence_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="指控只能使用已核验证据")

    def _public(self, session: GameSession) -> dict[str, Any]:
        return public_state(
            session.id,
            session.status,
            session.case_data,
            session.progress_data,
            session.generation_source,
            session.result_data,
        )

    @staticmethod
    def _get_session(db: Session, case_id: str) -> GameSession:
        session = db.get(GameSession, case_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案件不存在或已失效")
        return session
