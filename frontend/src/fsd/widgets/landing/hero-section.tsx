'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'

import { FspLoginButton } from '@/fsd/features/auth/fsp-login-button'
import { Button } from '@/fsd/shared/ui/button'

export function HeroSection() {
  return (
    <section id="hero" className="relative overflow-hidden px-4 pt-32 pb-16">
      {/* soft brand glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 mx-auto h-72 max-w-3xl rounded-full bg-primary/10 blur-3xl"
      />
      <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[1.2fr_1fr]">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="flex flex-col items-start gap-6"
        >
          <span className="rounded-pill border border-primary/30 bg-primary-soft px-3 py-1 text-xs font-medium tracking-wide text-primary">
            ФСП · ЛЦТ 2026 · обратная механика поиска
          </span>
          <h1 className="text-4xl font-extrabold text-balance text-heading sm:text-5xl">
            Работодатель находит вас сам
          </h1>
          <p className="max-w-xl text-lg text-pretty text-muted-foreground">
            PirateHunter — платформа-агрегатор ИТ-вакансий с обратной механикой. Кандидаты
            категоризированы по специализации и грейду, подтверждённому адаптивным тестом.
            Работодатель описывает потребность, получает объяснимую подборку и отправляет
            приглашение{' '}
            <strong className="text-foreground">с обязательной зарплатной вилкой</strong>. Контакты
            раскрываются только после принятия.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <FspLoginButton className="h-11 w-auto rounded-lg px-6 text-base" />
            <Link href="/login">
              <Button size="xl" variant="outline">
                Получить код на email
              </Button>
            </Link>
          </div>
        </motion.div>

        {/* Foreshadowing of the money screen: an invitation with the range up front */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut', delay: 0.15 }}
          className="hidden lg:block"
        >
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5 shadow-lg shadow-primary/5">
            <div className="flex items-center justify-between gap-3">
              <p className="font-semibold text-heading">ООО «Северный вектор»</p>
              <span className="rounded-pill bg-primary-soft px-3 py-1 text-xs font-medium text-primary">
                приглашение
              </span>
            </div>
            <p className="text-sm text-ink-2">
              Иван, увидели ваш подтверждённый middle по backend и диплом чемпионата ФСП…
            </p>
            <div className="rounded-lg bg-muted p-3">
              <p className="font-mono text-2xl font-semibold text-ink tabular-nums">
                220 000 – 280 000 ₽
              </p>
              <p className="text-xs text-muted-foreground">до вычета налогов · видна до ответа</p>
            </div>
            <div className="flex gap-2">
              <span className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
                Принять
              </span>
              <span className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground">
                Отклонить
              </span>
            </div>
            <p className="font-mono text-xs text-muted-foreground">
              контакты раскроются после принятия
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
