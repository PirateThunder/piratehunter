'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import { useSession } from '@/fsd/entities/session/model/session-store'
import type { User } from '@/fsd/entities/session/model/types'
import { DevLoginForm } from '@/fsd/features/auth/dev-login-form'
import { EmailLoginForm } from '@/fsd/features/auth/email-login-form'
import { FspLoginButton } from '@/fsd/features/auth/fsp-login-button'
import { ROLE_HOME } from '@/fsd/features/auth/lib/routes'
import { RoleSelect } from '@/fsd/features/auth/role-select'
import { env } from '@/fsd/shared/config/env'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/fsd/shared/ui/card'
import { Logo } from '@/fsd/shared/ui/logo'
import { Separator } from '@/fsd/shared/ui/separator'

/**
 * Sign-in: FSP ID (primary, PRD §7.1) or email code; role select on first
 * login. Already-authenticated users are routed to their cabinet.
 */
export function LoginPage() {
  const router = useRouter()
  const status = useSession((s) => s.status)
  const [needsRole, setNeedsRole] = useState(false)

  useEffect(() => {
    const { user } = useSession.getState()
    if (status === 'auth' && user?.role) router.replace(ROLE_HOME[user.role])
  }, [status, router])

  function handleDone(user: User) {
    if (user.role) router.replace(ROLE_HOME[user.role])
    else setNeedsRole(true)
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-secondary/50 px-4 py-8">
      <Card className="w-full max-w-md">
        <CardHeader className="items-center gap-3 text-center">
          <Link href="/" aria-label="PirateHunter — на главную">
            <Logo />
          </Link>
          <CardTitle className="text-xl">Вход в PirateHunter</CardTitle>
          <CardDescription>
            Работодатель находит вас сам — с вилкой зарплаты в первом же сообщении
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {needsRole ? (
            <RoleSelect />
          ) : (
            <>
              <FspLoginButton />
              <div className="flex items-center gap-3">
                <Separator className="flex-1" />
                <span className="text-xs text-muted-foreground">или</span>
                <Separator className="flex-1" />
              </div>
              <EmailLoginForm onDone={handleDone} />
              <p className="text-center text-xs text-muted-foreground">
                Входя через FSP ID или почту, вы принимаете{' '}
                <Link href="/terms" className="underline hover:text-foreground">
                  Условия использования
                </Link>{' '}
                и{' '}
                <Link href="/privacy" className="underline hover:text-foreground">
                  Политику конфиденциальности
                </Link>
              </p>
              {env.devLogin && (
                <>
                  <div className="flex items-center gap-3">
                    <Separator className="flex-1" />
                    <span className="text-xs text-muted-foreground">dev</span>
                    <Separator className="flex-1" />
                  </div>
                  <DevLoginForm onDone={handleDone} />
                </>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
