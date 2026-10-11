import { api } from '@/fsd/shared/api/http'
import type { Role } from '@/fsd/shared/api/types'

import type { AuthResponse, UserMe } from '../model/types'

/**
 * «Войти через FSP ID» (PRD §7.1): the backend builds the mock-OIDC
 * authorize URL (fsp_registry) — the browser is then redirected there.
 */
export interface FspAuthorizeOut {
  authorize_url: string
  state: string
}

export function fetchFspAuthorizeUrl() {
  return api.get('auth/fsp/authorize').json<FspAuthorizeOut>()
}

/** Email login, step 1: send a 6-digit code (uniform response). */
export function authEmailRequest(email: string) {
  return api
    .post('auth/email/request', { json: { email } })
    .json<{ detail: string; dev_code?: string | null }>()
}

/** Email login, step 2: verify the code, get the token pair. */
export function authEmailVerify(email: string, code: string) {
  return api.post('auth/email/verify', { json: { email, code } }).json<AuthResponse>()
}

/**
 * Dev-only login with fixed demo accounts (PRD §10):
 * 'candidate' | 'candidate-fsp' | 'employer'.
 */
export function authDev(account: string) {
  return api.post('auth/dev', { json: { account } }).json<AuthResponse>()
}

/** First-login role choice + 152-ФЗ consents (PRD §7.1). */
export function selectRole(role: Role, consentPublish: boolean) {
  return api
    .post('users/me/role', { json: { role, consent_pd: true, consent_publish: consentPublish } })
    .json<UserMe>()
}

export function logout() {
  return api
    .post('auth/logout')
    .json()
    .catch(() => {
      // Logout is best-effort: the local session is dropped regardless.
    })
}

export function fetchMe() {
  return api.get('users/me').json<UserMe>()
}
