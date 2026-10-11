'use client'

import { useState } from 'react'
import { toast } from 'sonner'

import { authDev } from '@/fsd/entities/session/api/auth-api'
import { useSession } from '@/fsd/entities/session/model/session-store'
import type { User } from '@/fsd/entities/session/model/types'
import { Button } from '@/fsd/shared/ui/button'

/**
 * Dev-only login with fixed demo accounts (PRD §10). Rendered only when
 * NEXT_PUBLIC_DEV_LOGIN=1 (stands/local); hidden in production builds.
 */
const DEMO_ACCOUNTS = [
  { account: 'candidate', label: 'Кандидат' },
  { account: 'candidate-fsp', label: 'Кандидат с ФСП' },
  { account: 'employer', label: 'Работодатель' },
] as const

export function DevLoginForm({ onDone }: { onDone: (user: User) => void }) {
  const [pending, setPending] = useState(false)

  const login = async (account: string) => {
    if (pending) return
    setPending(true)
    try {
      const data = await authDev(account)
      useSession.getState().setSession(data.user, data.access_token, data.expires_in)
      onDone(data.user)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось войти')
      setPending(false)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">Вход для разработки — демо-аккаунты</p>
      <div className="flex flex-wrap gap-2">
        {DEMO_ACCOUNTS.map(({ account, label }) => (
          <Button
            key={account}
            variant="secondary"
            className="flex-1 whitespace-normal"
            disabled={pending}
            onClick={() => void login(account)}
          >
            {label}
          </Button>
        ))}
      </div>
    </div>
  )
}
