'use client'

import { UsersRoundIcon } from 'lucide-react'
import { useState } from 'react'

import { ShortlistCard } from '@/fsd/entities/candidate/ui/shortlist-card'
import { InvitationForm } from '@/fsd/features/invitations/invitation-form'
import { cabinetApi } from '@/fsd/shared/api/cabinet-api'
import type { InvitationEmployer, Need } from '@/fsd/shared/api/types'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { EmptyState } from '@/fsd/shared/ui/empty-state'
import { Skeleton } from '@/fsd/shared/ui/skeleton'

/*
 * Shortlist for a need (money screen §7.11.1): ranked candidate cards with
 * the «Почему в подборке» panel; «рядом с запросом» (in_category=false) is
 * a separate block below (PRD §7.5.2).
 */
export function ShortlistPanel({ need }: { need: Need }) {
  const shortlist = useQuery(() => cabinetApi.employer.getShortlist(need.id), [need.id])
  const [inviteTarget, setInviteTarget] = useState<{ candidateId: string; name: string } | null>(
    null,
  )

  if (shortlist.loading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-36 w-full" />
        <Skeleton className="h-36 w-full" />
      </div>
    )
  }
  if (shortlist.error) {
    return (
      <EmptyState
        icon={UsersRoundIcon}
        title="Не удалось загрузить подборку"
        hint={shortlist.error.message}
      />
    )
  }

  const results = shortlist.data?.results ?? []
  const inCategory = results.filter((r) => r.in_category !== false)
  const nearby = results.filter((r) => r.in_category === false)

  return (
    <div className="flex flex-col gap-5">
      {results.length === 0 && (
        <EmptyState
          icon={UsersRoundIcon}
          title="Подборка пуста"
          hint="В категории пока нет кандидатов под этот запрос — попробуйте смягчить must-стек или грейд."
        />
      )}

      {inCategory.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">В категории запроса</h3>
          {inCategory.map((item, i) => (
            <ShortlistCard
              key={item.candidate.profile.candidate_id}
              item={item}
              defaultOpen={i === 0}
              onInvite={(candidateId, name) => setInviteTarget({ candidateId, name })}
            />
          ))}
        </div>
      )}

      {nearby.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold text-heading">Рядом с запросом</h3>
          <p className="text-sm text-muted-foreground">
            Вне целевой категории, но с сильным профилем (§7.5.2).
          </p>
          {nearby.map((item) => (
            <ShortlistCard
              key={item.candidate.profile.candidate_id}
              item={item}
              onInvite={(candidateId, name) => setInviteTarget({ candidateId, name })}
            />
          ))}
        </div>
      )}

      <InvitationForm
        target={inviteTarget}
        need={need}
        open={inviteTarget !== null}
        onOpenChange={(open) => !open && setInviteTarget(null)}
        onCreated={(_inv: InvitationEmployer) => {
          // The tracker refreshes on the dashboard; nothing to update here.
        }}
      />
    </div>
  )
}
