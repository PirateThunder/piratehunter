'use client'

import { useRouter } from 'next/navigation'
import { type ReactNode, useEffect } from 'react'

import { useSession } from '@/fsd/entities/session/model/session-store'

import { bootstrapSession } from './session-bootstrap'

/**
 * Cabinet guard: restores the session from the refresh cookie and redirects
 * anonymous users to /login. While the check runs, a spinner is shown.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter()
  const status = useSession((s) => s.status)

  useEffect(() => {
    if (useSession.getState().status !== 'unknown') return
    void bootstrapSession()
  }, [])

  useEffect(() => {
    if (status === 'guest') router.replace('/login')
  }, [status, router])

  if (status === 'auth') return children

  return (
    <output className="flex min-h-[60vh] items-center justify-center" aria-label="Загрузка">
      <span className="size-8 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
    </output>
  )
}
