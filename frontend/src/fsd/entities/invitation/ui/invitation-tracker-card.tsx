import type { InvitationEmployer } from '@/fsd/shared/api/types'
import { formatDateTime, GRADE_LABELS, SPEC_LABELS } from '@/fsd/shared/lib/format'
import { Card } from '@/fsd/shared/ui/card'
import { SalaryRange } from '@/fsd/shared/ui/salary-range'

import { InvitationStatusBadge } from './status-badge'

/*
 * Outgoing invitation in the employer tracker (§7.6): candidate + status
 * timeline (sent → viewed → accepted|declined); contacts after accept.
 */
export function InvitationTrackerCard({ invitation }: { invitation: InvitationEmployer }) {
  const { profile, contacts } = invitation.candidate
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-heading">{profile.fio}</p>
          <p className="text-xs text-muted-foreground">
            {profile.spec_slug ? (SPEC_LABELS[profile.spec_slug] ?? profile.spec_slug) : '—'}
            {profile.grade_verified ? ` · ${GRADE_LABELS[profile.grade_verified]}` : ''} ·{' '}
            {formatDateTime(invitation.created_at)}
          </p>
        </div>
        <InvitationStatusBadge status={invitation.status} />
      </div>

      <p className="text-sm text-pretty text-ink-2">{invitation.text}</p>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted p-3">
        <SalaryRange
          from={invitation.salary_from}
          to={invitation.salary_to}
          type={invitation.salary_type}
        />
        <span className="text-xs text-muted-foreground">связь: {invitation.contact_method}</span>
      </div>

      {invitation.status === 'accepted' && contacts && (
        <div className="rounded-lg bg-success-soft p-3">
          <p className="mb-1 text-sm font-medium text-success">Принято — контакты кандидата</p>
          <dl className="flex flex-wrap gap-x-6 gap-y-1 font-mono text-sm text-ink-2">
            {contacts.email && (
              <div>
                <dt className="inline text-muted-foreground">email: </dt>
                <dd className="inline">{contacts.email}</dd>
              </div>
            )}
            {contacts.phone && (
              <div>
                <dt className="inline text-muted-foreground">тел: </dt>
                <dd className="inline">{contacts.phone}</dd>
              </div>
            )}
            {Object.entries(contacts.contacts).map(([key, value]) => (
              <div key={key}>
                <dt className="inline text-muted-foreground">{key}: </dt>
                <dd className="inline">{String(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </Card>
  )
}
