import type {
  AccusationResult,
  AccusationReview,
  GameState,
  InterrogationResponse,
  InvestigationResponse,
  TheoryMap,
} from './types'

const API_ROOT = '/api'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  if (!response.ok) {
    let message = '请求失败，请稍后重试。'
    try {
      const body = (await response.json()) as { detail?: string }
      message = body.detail ?? message
    } catch {
      // Keep the safe generic message for non-JSON errors.
    }
    throw new ApiError(message, response.status)
  }
  return (await response.json()) as T
}

export const gameApi = {
  createCase: () => request<GameState>('/cases', { method: 'POST' }),

  getCase: (caseId: string) => request<GameState>(`/cases/${caseId}`),

  interrogate: (
    caseId: string,
    payload: {
      npc_id: string
      question: string
      presented_evidence_ids: string[]
      referenced_claim_ids?: string[]
      context_time?: string | null
      request_id: string
    },
  ) =>
    request<InterrogationResponse>(`/cases/${caseId}/interrogations`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  investigate: (
    caseId: string,
    payload: { evidence_id: string; action_type: string; request_id: string },
  ) =>
    request<InvestigationResponse>(`/cases/${caseId}/investigations`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  reviewAccusation: (
    caseId: string,
    payload: { suspect_id: string; theory: TheoryMap; request_id: string },
  ) =>
    request<AccusationReview>(`/cases/${caseId}/accusations/review`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  accuse: (
    caseId: string,
    payload: {
      suspect_id: string
      evidence_ids: string[]
      theory: TheoryMap
      reasoning_text: string
      request_id: string
    },
  ) =>
    request<AccusationResult>(`/cases/${caseId}/accusations/final`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
