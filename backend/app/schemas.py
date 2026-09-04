from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class PublicVictim(BaseModel):
    name: str
    role: str


class PublicBrief(BaseModel):
    title: str
    setting: str
    victim: PublicVictim
    location: str
    death_window: str
    summary: str
    public_timeline: list[dict[str, str]] = Field(default_factory=list)


class PublicSuspect(BaseModel):
    id: str
    name: str
    role: str
    initials: str
    public_bio: str
    personality: str
    interview_count: int = 0
    unverified_count: int = 0
    contradiction_count: int = 0
    pressure_state: str = "CALM"


class PublicEvidence(BaseModel):
    id: str
    title: str
    description: str
    source: str
    status: str
    verification_state: Literal[
        "UNVERIFIED", "REQUESTED", "VERIFIED", "CONTESTED", "INVALIDATED"
    ] = "UNVERIFIED"
    kind: str = "PHYSICAL_EVIDENCE"
    dimensions: list[str] = Field(default_factory=list)
    related_subject_ids: list[str] = Field(default_factory=list)
    action_type: str | None = None
    action_label: str = "核验来源"
    usable_in_accusation: bool = False


class DialogueEntry(BaseModel):
    id: str
    npc_id: str
    question: str
    response: str
    topic: str
    intent: str = "GENERAL"
    understanding: str = ""
    coverage: str = "DIRECT"
    reaction: str = "CALM"
    consumed_action: bool = True
    referenced_claim_ids: list[str] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    discovered_evidence_ids: list[str] = Field(default_factory=list)
    created_at: str


class NotebookSuspectSummary(BaseModel):
    npc_id: str
    interview_count: int
    unverified_count: int
    contradiction_count: int
    pressure_state: str


class Notebook(BaseModel):
    suspect_summaries: list[NotebookSuspectSummary] = Field(default_factory=list)
    contradictions: list[dict[str, str]] = Field(default_factory=list)
    timeline_entries: list[dict[str, Any]] = Field(default_factory=list)
    caught_claim_ids: list[str] = Field(default_factory=list)


class AccusationReview(BaseModel):
    coverage: dict[str, bool]
    feedback: list[str]
    used: bool = True


class EvidenceAnalysis(BaseModel):
    evidence_id: str
    title: str
    dimensions: list[str]
    mapped_to: list[str]


class AccusationResult(BaseModel):
    outcome: Literal["SOLVED", "INSUFFICIENT", "WRONG"]
    headline: str
    explanation: str
    culprit_id: str
    culprit_name: str
    motive: str
    method: str
    truth_summary: str
    truth_timeline: list[dict[str, str]]
    key_lies: list[dict[str, str]]
    selected_evidence_ids: list[str]
    evidence_analysis: list[EvidenceAnalysis] = Field(default_factory=list)
    player_theory: dict[str, list[str]] = Field(default_factory=dict)
    missing_dimensions: list[str]


class GameState(BaseModel):
    case_id: str
    schema_version: str = "2.0"
    status: Literal["ACTIVE", "REVIEWED", "SOLVED", "FAILED", "ABANDONED"]
    brief: PublicBrief
    suspects: list[PublicSuspect]
    evidence: list[PublicEvidence]
    messages: list[DialogueEntry]
    action_limit: int = 18
    actions_remaining: int = 18
    question_limit: int = 18
    questions_remaining: int = 18
    review_used: bool = False
    review: AccusationReview | None = None
    notebook: Notebook
    generation_source: Literal["kimi", "fallback"]
    result: AccusationResult | None = None


class InterrogationRequest(BaseModel):
    npc_id: str = Field(min_length=1, max_length=32)
    question: str = Field(min_length=1, max_length=500)
    presented_evidence_ids: list[str] = Field(default_factory=list, max_length=3)
    referenced_claim_ids: list[str] = Field(default_factory=list, max_length=3)
    context_time: str | None = Field(default=None, max_length=32)
    request_id: str = Field(min_length=8, max_length=80)

    @field_validator("question")
    @classmethod
    def trim_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("问题不能为空")
        return value


class InterrogationResponse(BaseModel):
    status: Literal["ANSWERED", "NEEDS_CLARIFICATION"] = "ANSWERED"
    entry: DialogueEntry | None = None
    new_evidence: list[PublicEvidence] = Field(default_factory=list)
    clarification_options: list[str] = Field(default_factory=list)
    understanding: str = ""
    consumed_action: bool = False
    actions_remaining: int
    questions_remaining: int
    notebook: Notebook


class InvestigationRequest(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=80)
    action_type: str = Field(min_length=1, max_length=40)
    request_id: str = Field(min_length=8, max_length=80)


class InvestigationResponse(BaseModel):
    evidence: PublicEvidence
    actions_remaining: int
    questions_remaining: int
    notebook: Notebook


class TheoryMap(BaseModel):
    motive: list[str] = Field(default_factory=list, max_length=2)
    method: list[str] = Field(default_factory=list, max_length=2)
    opportunity: list[str] = Field(default_factory=list, max_length=2)

    def all_evidence_ids(self) -> list[str]:
        return list(dict.fromkeys(self.motive + self.method + self.opportunity))


class AccusationReviewRequest(BaseModel):
    suspect_id: str = Field(min_length=1, max_length=32)
    theory: TheoryMap
    request_id: str = Field(min_length=8, max_length=80)


class AccusationRequest(BaseModel):
    suspect_id: str = Field(min_length=1, max_length=32)
    evidence_ids: list[str] = Field(default_factory=list, max_length=6)
    theory: TheoryMap | None = None
    reasoning_text: str = Field(default="", max_length=1200)
    request_id: str = Field(min_length=8, max_length=80)

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("证据不能重复选择")
        return value

    def selected_evidence_ids(self) -> list[str]:
        if self.theory:
            return self.theory.all_evidence_ids()
        return self.evidence_ids


class HealthResponse(BaseModel):
    status: str
    database: str
    kimi_configured: bool
    model: str
    engine_version: str = "truth-dialogue-v2"


CaseData = dict[str, Any]
