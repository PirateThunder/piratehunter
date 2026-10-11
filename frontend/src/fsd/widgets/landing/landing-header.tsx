import Link from 'next/link'

import { Button } from '@/fsd/shared/ui/button'
import { Logo } from '@/fsd/shared/ui/logo'

export function LandingHeader() {
  return (
    <header className="fixed top-0 right-0 left-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
        <a href="#hero" aria-label="PirateHunter — к началу страницы">
          <Logo className="h-7" />
        </a>
        <nav className="hidden items-center gap-6 md:flex" aria-label="Основная навигация">
          <a
            href="#candidate"
            className="text-sm text-muted-foreground transition-colors hover:text-primary"
          >
            Кандидатам
          </a>
          <a
            href="#employer"
            className="text-sm text-muted-foreground transition-colors hover:text-primary"
          >
            Работодателям
          </a>
        </nav>
        <Link href="/login">
          <Button size="sm">Войти</Button>
        </Link>
      </div>
    </header>
  )
}
