'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import { useSession } from '@/fsd/entities/session/model/session-store'
import { ROLE_HOME } from '@/fsd/features/auth/lib/routes'
import { RoleSelect } from '@/fsd/features/auth/role-select'
import { bootstrapSession } from '@/fsd/features/auth/session-bootstrap'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/fsd/shared/ui/card'

/**
 * Return point of the «Войти через FSP ID» flow: the backend has already set
 * the refresh cookie, so we restore the session and route by role (first
 * login → role choice).
 */
export function LoginCallbackPage() {
  const router = useRouter()
  const [failed, setFailed] = useState(false)
  const status = useSession((s) => s.status)

  useEffect(() => {
    void bootstrapSession().then(() => {
      if (useSession.getState().status === 'guest') setFailed(true)
    })
  }, [])

  useEffect(() => {
    const { user } = useSession.getState()
    if (status === 'auth' && user?.role) router.replace(ROLE_HOME[user.role])
  }, [status, router])

  return (
    <main className="flex min-h-screen items-center justify-center bg-secondary/50 px-4 py-8">
      <Card className="w-full max-w-md">
        <CardHeader className="items-center gap-2 text-center">
          <CardTitle className="text-xl">Вход через FSP ID</CardTitle>
          <CardDescription>
            {failed ? 'Не удалось завершить вход' : 'Завершаем вход…'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {failed ? (
            <a href="/login" className="text-center text-primary hover:underline">
              Вернуться ко входу
            </a>
          ) : status === 'auth' && !useSession.getState().user?.role ? (
            <RoleSelect />
          ) : (
            <output className="flex items-center justify-center py-4" aria-label="Загрузка">
              <span className="size-8 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
            </output>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
