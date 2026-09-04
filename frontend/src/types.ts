export type GameStatus = 'ACTIVE' | 'REVIEWED' | 'SOLVED' | 'FAILED' | 'ABANDONED'
export type EvidenceState =
  | 'UNVERIFIED'
  | 'REQUESTED'
  | 'VERIFIED'
  | 'CONTESTED'
  | 'INVALIDATED'

export interface Victim {
  name: string
  role: string
}

export interface Brief {
  title: string
  setting: string
  victim: Victim
  location: string
  death_window: string
  summary: string
  public_timeline: Array<{ time: string; event: string }>
}

export interface Suspect {
  id: string
  name: string
  role: string
  initials: string
  public_bio: string
  personality: string
  interview_count: number
  unverified_count: number
  contradiction_count: number
  pressure_state: string
}

export interface Evidence {
  id: string
  title: string
  description: string
  source: string
  status: string
  verification_state: EvidenceState
  kind: string
  dimensions: string[]
  related_subject_ids: string[]
  action_type: string | null
  action_label: string
  usable_in_accusation: boolean
}

export interface DialogueEntry {
  id: string
  npc_id: string
  question: string
  response: string
  topic: string
  intent: string
  understanding: string
  coverage: string
  reaction: string
  consumed_action: boolean
  referenced_claim_ids: string[]
  suggested_followups: string[]
  discovered_evidence_ids: string[]
  created_at: string
}

export interface Notebook {
  suspect_summaries: Array<{
    npc_id: string
    interview_count: number
    unverified_count: number
    contradiction_count: number
    pressure_state: string
  }>
  contradictions: Array<{
    id: string
    npc_id: string
    claim: string
    evidence_id: string
    label: string
  }>
  timeline_entries: Array<{ time: string; event: string; status?: string }>
  caught_claim_ids: string[]
}

export interface TheoryMap {
  motive: string[]
  method: string[]
  opportunity: string[]
}

export interface AccusationReview {
  coverage: Record<string, boolean>
  feedback: string[]
  used: boolean
}

export interface AccusationResult {
  outcome: 'SOLVED' | 'INSUFFICIENT' | 'WRONG'
  headline: string
  explanation: string
  culprit_id: string
  culprit_name: string
  motive: string
  method: string
  truth_summary: string
  truth_timeline: Array<{ time: string; event: string }>
  key_lies: Array<{
    claim_id: string
    speaker: string
    claim: string
    truth: string
    discovery_status: 'CAUGHT' | 'HEARD' | 'MISSED'
  }>
  selected_evidence_ids: string[]
  evidence_analysis: Array<{
    evidence_id: string
    title: string
    dimensions: string[]
    mapped_to: string[]
  }>
  player_theory: TheoryMap | Record<string, string[]>
  missing_dimensions: string[]
}

export interface GameState {
  case_id: string
  schema_version: string
  status: GameStatus
  brief: Brief
  suspects: Suspect[]
  evidence: Evidence[]
  messages: DialogueEntry[]
  action_limit: number
  actions_remaining: number
  question_limit: number
  questions_remaining: number
  review_used: boolean
  review: AccusationReview | null
  notebook: Notebook
  generation_source: 'kimi' | 'fallback'
  result: AccusationResult | null
}

export interface InterrogationResponse {
  status: 'ANSWERED' | 'NEEDS_CLARIFICATION'
  entry: DialogueEntry | null
  new_evidence: Evidence[]
  clarification_options: string[]
  understanding: string
  consumed_action: boolean
  actions_remaining: number
  questions_remaining: number
  notebook: Notebook
}

export interface InvestigationResponse {
  evidence: Evidence
  actions_remaining: number
  questions_remaining: number
  notebook: Notebook
}
