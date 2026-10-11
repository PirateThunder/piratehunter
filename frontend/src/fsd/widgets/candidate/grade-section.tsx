'use client'

import Link from 'next/link'

import { fetchCatalog } from '@/fsd/entities/catalog/api/catalog-api'
import type { CandidateSelf, GradeInfo } from '@/fsd/shared/api/types'
import { formatDate, GRADE_STATUS_LABELS, gradeLabel, specLabel } from '@/fsd/shared/lib/format'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { Badge } from '@/fsd/shared/ui/badge'
import { Button } from '@/fsd/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/fsd/shared/ui/card'

/*
 * Candidate category screen (money screen §7.11.4): spec × grade, «подтверждено
 * тестом от <дата>», rank inside the category, cooldowns, ФСП achievements block.
 */
export function GradeSection({
  grade,
  profile,
}: {
  grade: GradeInfo
  profile: CandidateSelf | null
}) {
  const catalog = useQuery(() => fetchCatalog())

  const now = Date.now()
  const retestAt = grade.retest_available_at ? Date.parse(grade.retest_available_at) : null
  const changeAt = grade.change_available_at ? Date.parse(grade.change_available_at) : null
  const canRetest = !retestAt || retestAt <= now
  const canChange = !changeAt || changeAt <= now
  const fsp = profile?.fsp ?? null

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Ваша категория</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-xl">
            <span className="font-semibold text-heading">
              {specLabel(catalog.data, grade.spec_slug)}
            </span>
            {' × '}
            <span className="font-semibold text-heading">
              {grade.grade_verified
                ? gradeLabel(catalog.data, grade.grade_verified)
                : 'грейд не подтверждён'}
            </span>
          </p>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={grade.status === 'confirmed' ? 'success' : 'outline'}>
              {GRADE_STATUS_LABELS[grade.status]}
            </Badge>
            {grade.last_test_at && (
              <span className="text-sm text-muted-foreground">
                тест от {formatDate(grade.last_test_at)}
              </span>
            )}
            {grade.theta != null && (
              <span className="font-mono text-sm text-muted-foreground tabular-nums">
                θ={grade.theta.toFixed(2)}
              </span>
            )}
          </div>

          {grade.category_rank != null && grade.category_size != null && (
            <p className="rounded-lg bg-muted p-3 text-sm text-ink-2">
              Место в категории:{' '}
              <span className="font-mono font-semibold text-ink tabular-nums">
                {grade.category_rank} из {grade.category_size}
              </span>{' '}
              — выше стоят сильнее подтверждённые профили с достижениями ФСП
            </p>
          )}

          {grade.status === 'unverified' && (
            <p className="rounded-lg bg-primary-soft p-3 text-sm text-ink-2">
              Профиль показывается со статусом «не подтверждён» и ниже в выдаче. Пройдите тест —
              категория присваивается сразу после него.
            </p>
          )}
          {grade.status === 'upgrade_offer' && (
            <p className="rounded-lg bg-success-soft p-3 text-sm text-ink-2">
              Уверенный результат! Доступен тест на повышение грейда.
            </p>
          )}
          {grade.status === 'downgrade_offer' && (
            <p className="rounded-lg bg-muted p-3 text-sm text-ink-2">
              Тест не дотянул до заявленного грейда — грейд не понижается принудительно. Можно
              пройти тест на уровень ниже (попытка не сгорает) или пересдать позже.
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            <Link href="/candidate/test">
              <Button>Пройти тест</Button>
            </Link>
          </div>
          <p className="text-xs text-muted-foreground">
            {canRetest
              ? 'Пересдача текущего грейда доступна.'
              : grade.retest_available_at
                ? `Пересдача — с ${formatDate(grade.retest_available_at)}.`
                : ''}{' '}
            {canChange
              ? 'Смена подтверждённого грейда доступна.'
              : grade.change_available_at
                ? `Смена грейда — с ${formatDate(grade.change_available_at)}.`
                : ''}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Достижения ФСП</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {profile?.fsp_id ? (
            fsp ? (
              <>
                <p className="text-sm text-muted-foreground">
                  FSP ID <span className="font-mono text-ink">{profile.fsp_id}</span> · вклад в
                  ранжирование{' '}
                  <span className="font-mono font-semibold text-primary tabular-nums">
                    {fsp.score.toFixed(2)}
                  </span>
                </p>
                <FspAchievements achievements={fsp.achievements} />
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                FSP ID {profile.fsp_id} привязан, но история достижений не найдена — блок скрыт из
                профиля, штрафа сверх нулевого вклада нет (§7.9).
              </p>
            )
          ) : (
            <p className="text-sm text-muted-foreground">
              Привяжите ФСП ID в настройках — дипломы и разряды усилят позицию в выдаче.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

/** Compact renderer of the registry document (rating, ranks, contests, events). */
function FspAchievements({ achievements }: { achievements: Record<string, unknown> }) {
  const rating = typeof achievements.rating === 'number' ? achievements.rating : null
  const contests = Array.isArray(achievements.contests) ? achievements.contests : []
  const ranks = Array.isArray(achievements.ranks) ? achievements.ranks : []
  return (
    <ul className="flex flex-col gap-1.5 text-sm text-ink-2">
      {rating != null && (
        <li>
          Рейтинг: <span className="font-mono tabular-nums">{rating}</span>
        </li>
      )}
      {ranks.slice(0, 5).map((rank, i) => {
        const r = rank as { discipline?: string; rank?: string }
        const text = [r.discipline, r.rank].filter(Boolean).join(' — ')
        return <li key={`rank-${i}-${text}`}>Разряд: {text}</li>
      })}
      {contests.slice(0, 5).map((contest, i) => {
        const c = contest as { name?: string; place?: number; diploma?: number | null }
        return (
          <li key={`contest-${i}-${c.name ?? ''}`}>
            {c.name}
            {c.place ? `, место ${c.place}` : ''}
            {c.diploma ? `, диплом ${c.diploma} степени` : ''}
          </li>
        )
      })}
    </ul>
  )
}
