'use client'

import { MailPlusIcon } from 'lucide-react'

import { InvitationInboxCard } from '@/fsd/entities/invitation/ui/invitation-inbox-card'
import type { InvitationCandidate } from '@/fsd/shared/api/types'
import { EmptyState } from '@/fsd/shared/ui/empty-state'

/** Inbox of incoming invitations (money screen §7.11.3). */
export function InvitationsSection({
  invitations,
  onChanged,
}: {
  invitations: InvitationCandidate[]
  onChanged: (updated: InvitationCandidate) => void
}) {
  if (invitations.length === 0) {
    return (
      <EmptyState
        icon={MailPlusIcon}
        title="Пока нет входящих приглашений"
        hint="Работодатели видят ваш профиль в категории после подтверждения грейда тестом. Вилка зарплаты будет видна до ответа."
      />
    )
  }
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Вилка зарплаты и условия видны до ответа — принципиальное отличие платформы.
      </p>
      {invitations.map((invitation) => (
        <InvitationInboxCard key={invitation.id} invitation={invitation} onChanged={onChanged} />
      ))}
    </div>
  )
}
