import type { CandidateEmployer } from '@/fsd/shared/api/types'
import { GRADE_LABELS, GRADE_STATUS_LABELS, SPEC_LABELS } from '@/fsd/shared/lib/format'
import { Badge } from '@/fsd/shared/ui/badge'
import { Button } from '@/fsd/shared/ui/button'
import { Card } from '@/fsd/shared/ui/card'

/** Compact candidate card for the employer bank (PRD §7.3 «Банк кандидатов»). */
export function CandidateCard({
  candidate,
  onInvite,
}: {
  candidate: CandidateEmployer
  onInvite?: (candidateId: string, name: string) => void
}) {
  const { profile } = candidate
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-heading">{profile.fio}</p>
          <p className="text-xs text-muted-foreground">
            {profile.spec_slug ? (SPEC_LABELS[profile.spec_slug] ?? profile.spec_slug) : '—'}
            {profile.grade_verified
              ? ` · ${GRADE_LABELS[profile.grade_verified]}`
              : profile.grade_claimed
                ? ` · заявлен ${GRADE_LABELS[profile.grade_claimed]}`
                : ''}
            {profile.experience_years != null ? ` · стаж ${profile.experience_years} г.` : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {profile.grade_status === 'unverified' || !profile.grade_verified ? (
            <Badge variant="outline">{GRADE_STATUS_LABELS.unverified}</Badge>
          ) : (
            <Badge variant="success">{GRADE_STATUS_LABELS.confirmed}</Badge>
          )}
          {profile.has_fsp && <Badge variant="accent">ФСП</Badge>}
        </div>
      </div>
      {profile.about && <p className="mt-1 line-clamp-2 text-sm text-ink-2">{profile.about}</p>}
      <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Стек">
        {profile.stack.map((tech) => (
          <li key={tech}>
            <Badge>{tech}</Badge>
          </li>
        ))}
      </ul>
      {onInvite && (
        <div className="mt-3 flex justify-end">
          <Button size="sm" onClick={() => onInvite(profile.candidate_id, profile.fio)}>
            Пригласить
          </Button>
        </div>
      )}
    </Card>
  )
}
