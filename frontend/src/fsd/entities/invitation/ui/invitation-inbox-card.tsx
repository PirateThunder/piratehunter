'use client'

import { useState } from 'react'
import { toast } from 'sonner'

import { acceptInvitation, declineInvitation } from '@/fsd/entities/candidate/api/candidate-api'
import type { InvitationCandidate } from '@/fsd/shared/api/types'
import { formatDateTime } from '@/fsd/shared/lib/format'
import { Button } from '@/fsd/shared/ui/button'
import { Card } from '@/fsd/shared/ui/card'
import { SalaryRange } from '@/fsd/shared/ui/salary-range'

import { InvitationStatusBadge } from './status-badge'

function ContactsBlock({ contacts }: { contacts: Record<string, unknown> }) {
  return (
    <dl className="flex flex-wrap gap-x-6 gap-y-1 font-mono text-sm text-ink-2">
      {Object.entries(contacts).map(([key, value]) => (
        <div key={key}>
          <dt className="inline text-muted-foreground">{key}: </dt>
          <dd className="inline">{String(value)}</dd>
        </div>
      ))}
    </dl>
  )
}

/*
 * Incoming invitation (money screen §7.11.3): company, text, salary range
 * up front — visible BEFORE the answer (the platform's core principle).
 * After accept — contacts of both sides revealed (§7.6).
 */
export function InvitationInboxCard({
  invitation,
  onChanged,
}: {
  invitation: InvitationCandidate
  onChanged: (updated: InvitationCandidate) => void
}) {
  const [pending, setPending] = useState(false)
  const { company, contacts } = invitation.company
  const answered = invitation.status === 'accepted' || invitation.status === 'declined'

  async function respond(action: 'accept' | 'decline') {
    if (pending) return
    setPending(true)
    try {
      if (action === 'accept') {
        const data = await acceptInvitation(invitation.id)
        onChanged(data.invitation)
        toast.success('Приглашение принято — контакты раскрыты обеим сторонам')
      } else {
        const updated = await declineInvitation(invitation.id)
        onChanged(updated)
        toast.success('Приглашение отклонено')
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось ответить на приглашение')
    } finally {
      setPending(false)
    }
  }

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-heading">{company.name}</p>
          <p className="text-xs text-muted-foreground">
            {formatDateTime(invitation.created_at)} · связь: {invitation.contact_method}
            {company.industry ? ` · ${company.industry}` : ''}
          </p>
        </div>
        <InvitationStatusBadge status={invitation.status} />
      </div>

      <p className="text-sm text-pretty text-ink-2">{invitation.text}</p>

      <div className="rounded-xl bg-muted p-4">
        <SalaryRange
          from={invitation.salary_from}
          to={invitation.salary_to}
          type={invitation.salary_type}
          size="lg"
        />
      </div>

      {invitation.status === 'accepted' ? (
        <div className="flex flex-col gap-2 rounded-xl bg-success-soft p-4">
          <p className="text-sm font-medium text-success">
            Приглашение принято — контакты раскрыты обеим сторонам
          </p>
          {contacts && <ContactsBlock contacts={contacts.contacts} />}
          <p className="text-xs text-muted-foreground">
            Ваши контакты также переданы компании {company.name}.
          </p>
        </div>
      ) : (
        !answered && (
          <div className="flex flex-wrap gap-2">
            <Button disabled={pending} onClick={() => void respond('accept')}>
              Принять
            </Button>
            <Button variant="outline" disabled={pending} onClick={() => void respond('decline')}>
              Отклонить
            </Button>
          </div>
        )
      )}
    </Card>
  )
}
