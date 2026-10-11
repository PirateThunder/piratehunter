import { create } from 'zustand'

import type { User } from './types'

/**
 * Session state. The access token lives ONLY in memory (never localStorage):
 * a page reload re-authenticates via the httpOnly refresh cookie.
 * `status` distinguishes "not checked yet" (unknown) from "checked, anonymous".
 */
type SessionStatus = 'unknown' | 'auth' | 'guest'

interface SessionState {
  user: User | null
  accessToken: string | null
  /** Epoch ms when the access token expires. */
  expiresAt: number
  status: SessionStatus
  setSession: (user: User | null, accessToken: string, expiresIn: number) => void
  setToken: (accessToken: string, expiresIn: number) => void
  setUser: (user: User) => void
  setGuest: () => void
  clear: () => void
}

export const useSession = create<SessionState>()((set) => ({
  user: null,
  accessToken: null,
  expiresAt: 0,
  status: 'unknown',
  setSession: (user, accessToken, expiresIn) =>
    set({ user, accessToken, expiresAt: Date.now() + expiresIn * 1000, status: 'auth' }),
  setToken: (accessToken, expiresIn) =>
    set({ accessToken, expiresAt: Date.now() + expiresIn * 1000 }),
  setUser: (user) => set({ user }),
  setGuest: () => set({ user: null, accessToken: null, expiresAt: 0, status: 'guest' }),
  clear: () => set({ user: null, accessToken: null, expiresAt: 0, status: 'guest' }),
}))

/** Non-reactive accessor for the ky hooks. */
export const getSession = () => useSession.getState()
