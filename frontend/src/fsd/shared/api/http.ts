import ky, { HTTPError, type KyInstance } from 'ky'

import { getSession } from '@/fsd/entities/session/model/session-store'

/**
 * Shared ky instance for the backend API.
 *
 * - Base is the same-origin `/api/v1`; next.config rewrites proxy it to the
 *   backend, so the refresh cookie (path=/api/v1/auth) stays first-party.
 * - Every request carries the in-memory Bearer token.
 * - On 401 (outside /auth/*) a single-flight refresh runs and the request is
 *   force-retried once with the fresh token; a failed refresh drops the
 *   session, and the AuthGate reacts by routing to /login.
 * - Error bodies are unwrapped by re-throwing an HTTPError from afterResponse
 *   (ky2 has already consumed the body in beforeError, and hook-thrown plain
 *   Errors get wrapped into a generic network error when a retry limit is
 *   set): `{error:{code,message}}`, string `{detail}` and FastAPI's
 *   `[{msg}]` array surface as the thrown error's message.
 */

interface RefreshResponse {
  access_token: string
  expires_in: number
}

/** Hook-free instance for auth calls themselves (no Bearer, no 401 retry). */
const bareKy = ky.create({ retry: 0, timeout: 30_000 })

let refreshPromise: Promise<boolean> | null = null

/** Single-flight token refresh via the httpOnly refresh cookie. */
export function refreshSession(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const data = await bareKy
          .post('/api/v1/auth/refresh', { credentials: 'include' })
          .json<RefreshResponse>()
        getSession().setToken(data.access_token, data.expires_in)
        return true
      } catch {
        getSession().clear()
        return false
      } finally {
        // Allow the next 401 to trigger a fresh attempt.
        setTimeout(() => {
          refreshPromise = null
        }, 0)
      }
    })()
  }
  return refreshPromise
}

/** Reads the readable message out of an error response body. */
async function errorMessage(response: Response): Promise<string | undefined> {
  try {
    const body = (await response.clone().json()) as {
      error?: { message?: string }
      detail?: unknown
    }
    if (typeof body?.error?.message === 'string' && body.error.message) return body.error.message
    if (typeof body?.detail === 'string' && body.detail) return body.detail
    if (Array.isArray(body?.detail)) {
      const first = body.detail[0] as { msg?: string } | undefined
      if (first?.msg) return first.msg
    }
  } catch {
    // Non-JSON error body — the caller keeps ky's default message.
  }
  return undefined
}

export const api: KyInstance = ky.create({
  prefix: '/api/v1',
  credentials: 'include',
  // Automatic retries off (shouldRetry: false); the 401 handler force-retries
  // explicitly via ky.retry(), which is exempt from shouldRetry.
  retry: { limit: 2, shouldRetry: () => false },
  timeout: 30_000,
  hooks: {
    beforeRequest: [
      ({ request }) => {
        const { accessToken } = getSession()
        if (accessToken) request.headers.set('Authorization', `Bearer ${accessToken}`)
      },
    ],
    afterResponse: [
      async ({ request, response, options, retryCount }) => {
        if (response.status === 401) {
          if (new URL(request.url).pathname.includes('/auth/')) return
          if (retryCount > 0) return
          if (!(await refreshSession())) return
          const { accessToken } = getSession()
          const headers = new Headers(request.headers)
          if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
          return ky.retry({ request: new Request(request, { headers }), code: 'TOKEN_REFRESHED' })
        }
        if (!response.ok) {
          const message = await errorMessage(response)
          if (message) {
            const error = new HTTPError(response, request, options)
            error.message = message
            throw error
          }
        }
      },
    ],
  },
})
