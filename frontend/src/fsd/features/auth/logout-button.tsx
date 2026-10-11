'use client'

import { LogOutIcon } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { logout } from '@/fsd/entities/session/api/auth-api'
import { useSession } from '@/fsd/entities/session/model/session-store'
import { Button } from '@/fsd/shared/ui/button'

export function LogoutButton() {
  const router = useRouter()
  const [pending, setPending] = useState(false)

  const handleLogout = async () => {
    if (pending) return
    setPending(true)
    await logout()
    useSession.getState().clear()
    router.replace('/login')
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => void handleLogout()}
      disabled={pending}
      aria-label="Выйти из аккаунта"
    >
      <LogOutIcon />
      <span className="hidden sm:inline">Выйти</span>
    </Button>
  )
}
