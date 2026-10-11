'use client'

import { BriefcaseIcon } from 'lucide-react'

import type { ApplicationCandidate } from '@/fsd/shared/api/types'
import { formatDate } from '@/fsd/shared/lib/format'
import { Badge } from '@/fsd/shared/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/fsd/shared/ui/card'
import { EmptyState } from '@/fsd/shared/ui/empty-state'
import { SalaryRange } from '@/fsd/shared/ui/salary-range'

const STATUS_LABELS: Record<ApplicationCandidate['status'], string> = {
  sent: 'Отправлен',
  viewed: 'Просмотрен',
  invited: 'Приглашение',
  rejected: 'Отклонён',
}

/** Candidate's own applications (PRD §7.7). */
export function MyApplicationsSection({ applications }: { applications: ApplicationCandidate[] }) {
  if (applications.length === 0) {
    return (
      <EmptyState
        icon={BriefcaseIcon}
        title="Вы пока никуда не откликались"
        hint="Во вкладке «Вакансии» откройте подходящую — отклик открывает работодателю ваш профиль."
      />
    )
  }
  return (
    <div className="flex flex-col gap-4">
      {applications.map((a) => (
        <Card key={a.id}>
          <CardHeader className="gap-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base">{a.vacancy.title}</CardTitle>
              <Badge variant={a.status === 'invited' ? 'success' : 'outline'}>
                {STATUS_LABELS[a.status]}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              {a.company.company.name} · отклик от {formatDate(a.created_at)}
            </p>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <SalaryRange
              from={a.vacancy.salary_from}
              to={a.vacancy.salary_to}
              type={a.vacancy.salary_type}
            />
            {a.message && <p className="text-sm text-ink-2">{a.message}</p>}
            {a.status === 'invited' && a.company.contacts ? (
              <p className="text-sm">
                Контакты компании открыты:{' '}
                <span className="font-medium">
                  {Object.values(a.company.contacts.contacts ?? {}).join(' · ') ||
                    'см. профиль компании'}
                </span>
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Контакты компании откроются, если работодатель пригласит вас на интервью.
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
