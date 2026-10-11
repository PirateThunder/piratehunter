import Link from 'next/link'

import { Logo } from '@/fsd/shared/ui/logo'

export function LandingFooter() {
  return (
    <footer className="bg-ink text-background">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-10 md:flex-row md:items-start md:justify-between">
        <div className="flex flex-col gap-3">
          <Logo variant="white" />
          <p className="max-w-sm text-sm text-placeholder">
            PirateHunter — платформа-агрегатор ИТ-вакансий с обратной механикой. Хакатон ЛЦТ 2026,
            спец. трек ФСП.
          </p>
        </div>
        <nav aria-label="Навигация в подвале" className="flex flex-col gap-2 text-sm">
          <Link href="/login" className="text-background/80 hover:text-background">
            Войти
          </Link>
          <Link href="/candidate" className="text-background/80 hover:text-background">
            Кабинет кандидата
          </Link>
          <Link href="/employer" className="text-background/80 hover:text-background">
            Кабинет работодателя
          </Link>
        </nav>
      </div>
      <div className="border-t border-background/10">
        <p className="mx-auto max-w-6xl px-4 py-4 font-mono text-xs text-placeholder">
          © 2026 · контакты кандидатов раскрываются только после принятия приглашения
        </p>
      </div>
    </footer>
  )
}
