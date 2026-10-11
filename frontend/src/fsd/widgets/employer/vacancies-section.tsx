'use client'

import { BriefcaseIcon } from 'lucide-react'
import Link from 'next/link'

import type { Vacancy } from '@/fsd/shared/api/types'
import { formatDate, formatSalary } from '@/fsd/shared/lib/format'
import { Badge } from '@/fsd/shared/ui/badge'
import { Button } from '@/fsd/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/fsd/shared/ui/card'
import { EmptyState } from '@/fsd/shared/ui/empty-state'

const STATUS_LABELS: Record<Vacancy['status'], string> = {
  draft: 'Черновик',
  published: 'Опубликована',
  closed: 'Закрыта',
}

/** Employer's vacancies on the dashboard (PRD §7.7). */
export function VacanciesSection({ vacancies }: { vacancies: Vacancy[] }) {
  return (
    <section className="flex flex-col gap-3" aria-labelledby="vacancies-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="vacancies-heading" className="text-lg font-semibold text-heading">
          Вакансии
        </h2>
        <Link href="/employer/vacancies">
          <Button variant="outline">Все вакансии</Button>
        </Link>
      </div>
      {vacancies.length === 0 && (
        <EmptyState
          icon={BriefcaseIcon}
          title="Нет вакансий"
          hint="Публикация вакансии открывает кандидатам возможность откликнуться самим — инициатива работает в обе стороны."
          action={
            <Link href="/employer/vacancies">
              <Button>Создать вакансию</Button>
            </Link>
          }
        />
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {vacancies.slice(0, 4).map((v) => (
          <Card key={v.id}>
            <CardHeader className="gap-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="text-base">{v.title}</CardTitle>
                <Badge variant={v.status === 'published' ? 'success' : 'outline'}>
                  {STATUS_LABELS[v.status]}
                </Badge>
              </div>
              <p className="font-mono text-sm text-ink-2">
                {formatSalary(v.salary_from, v.salary_to)} ·{' '}
                {v.salary_type === 'gross' ? 'gross' : 'net'}
              </p>
            </CardHeader>
            <CardContent className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                создана {formatDate(v.created_at)}
              </span>
              <Link href={`/employer/vacancies/${v.id}`}>
                <Button variant="secondary">Открыть</Button>
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}
