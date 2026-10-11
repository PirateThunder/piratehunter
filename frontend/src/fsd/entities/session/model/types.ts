import type { Role } from '@/fsd/shared/api/types'

/** Session user (AuthUserOut of POST /auth/*). */
export interface User {
  id: string
  email: string | null
  fsp_id: string | null
  /** null until the first-login role choice (PRD §7.1) */
  role: Role | null
  is_verified: boolean
}

/** GET /users/me adds consents on top of the auth user. */
export interface UserMe extends User {
  consent_pd: boolean
  consent_publish: boolean
  created_at: string
}

/** POST /auth/* response shape (pair + profile; refresh omits user). */
export interface AuthResponse {
  user: User
  access_token: string
  expires_in: number
}
