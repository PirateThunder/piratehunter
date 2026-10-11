'use client'

import { useRouter } from 'next/navigation'
import { type ReactNode, useEffect } from 'react'

import { useSession } from '@/fsd/entities/session/model/session-store'
import type { Role } from '@/fsd/shared/api/types'

import { ROLE_HOME } from './lib/routes'

/**
 * Role guard inside the cabinet group: a user whose role doesn't match the
 * section is routed to their own cabinet; users without a role (onboarding
 * not finished) go back to /login for the role choice.
 */
export function RoleGate({ allowedRole, children }: { allowedRole: Role; children: ReactNode }) {
  const router = useRouter()
  const user = useSession((s) => s.user)

  useEffect(() => {
    if (!user) return
    if (!user.role) router.replace('/login')
    else if (user.role !== allowedRole) router.replace(ROLE_HOME[user.role])
  }, [user, allowedRole, router])

  if (!user || user.role !== allowedRole) {
    return (
      <output className="flex min-h-[40vh] items-center justify-center" aria-label="Загрузка">
        <span className="size-8 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
      </output>
    )
  }
  return children
}
