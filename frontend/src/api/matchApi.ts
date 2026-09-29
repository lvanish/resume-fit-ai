import type { MatchRequest, MatchResponse } from '../types.ts'

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (typeof configured !== 'string' || configured.trim() === '') {
    return ''
  }
  return configured.replace(/\/+$/, '')
}

function isErrorBody(value: unknown): value is { message: string } {
  if (typeof value !== 'object' || value === null || !('message' in value)) {
    return false
  }
  return typeof value.message === 'string' && value.message.trim().length > 0
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (isErrorBody(body)) {
      return body.message
    }
  } catch {
    // Response was not JSON.
  }
  return `Analysis request failed (${response.status}).`
}

export async function analyzeMatch(request: MatchRequest): Promise<MatchResponse> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl()}/api/v1/match`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
  } catch {
    throw new Error('Could not reach the ResumeFit API. Check that the backend is running.')
  }

  if (!response.ok) {
    throw new Error(await readErrorMessage(response))
  }

  const body: unknown = await response.json()
  if (!isMatchResponse(body)) {
    throw new Error('The API returned an unexpected match result.')
  }
  return body
}

function isMatchResponse(value: unknown): value is MatchResponse {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const score = (value as { score?: unknown }).score
  return typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 100
}
