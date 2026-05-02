import type { BeanProfile, TasteProfile, RecommendationResponse, RecommendationRun } from './types'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    super(`API error ${status}`)
    this.status = status
    this.body = body
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init)
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, body)
  return body as T
}

export function createUser(userId: string): Promise<{ user_id: string }> {
  return request('/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId }),
  })
}

export function addBeans(userId: string, inputs: string[], userScore: number): Promise<{ parsed: BeanProfile[]; skipped: string[] }> {
  return request('/beans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, inputs, user_score: userScore }),
  })
}

export function getBeans(userId: string): Promise<BeanProfile[]> {
  return request(`/beans?user_id=${encodeURIComponent(userId)}`)
}

export function getProfile(userId: string): Promise<TasteProfile> {
  return request(`/profile?user_id=${encodeURIComponent(userId)}`)
}

export function getRecommendations(userId: string, n = 5): Promise<RecommendationResponse> {
  return request(`/recommendations?user_id=${encodeURIComponent(userId)}&n=${n}`)
}

export function getRecommendationRuns(userId: string): Promise<RecommendationRun[]> {
  return request(`/recommendation-runs?user_id=${encodeURIComponent(userId)}`)
}
