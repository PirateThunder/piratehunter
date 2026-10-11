'use client'

import Link from 'next/link'
import type { ReactNode } from 'react'

import { useSession } from '@/fsd/entities/session/model/session-store'
import { LogoutButton } from '@/fsd/features/auth/logout-button'
import { Badge } from '@/fsd/shared/ui/badge'
import { Logo } from '@/fsd/shared/ui/logo'

/** Cabinet chrome: top header with logo, role badge, user and logout. */
export function AppChrome({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-secondary/50">
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>
    </div>
  )
}

function AppHeader() {
  const user = useSession((s) => s.user)

  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4">
        <Link href="/" aria-label="PirateHunter — на главную">
          <Logo className="h-7" />
        </Link>
        <div className="flex items-center gap-2">
          {user?.role && (
            <Badge variant="accent">
              {user.role === 'candidate' ? 'Кандидат' : 'Работодатель'}
            </Badge>
          )}
          {user?.email && (
            <span
              className="hidden max-w-48 truncate text-sm text-muted-foreground md:inline"
              title={user.email}
            >
              {user.email}
            </span>
          )}
          <LogoutButton />
        </div>
      </div>
    </header>
  )
}
