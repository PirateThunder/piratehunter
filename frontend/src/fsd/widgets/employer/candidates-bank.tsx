'use client'

import { ChevronLeftIcon, ChevronRightIcon, SearchXIcon } from 'lucide-react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useState } from 'react'

import { CandidateCard } from '@/fsd/entities/candidate/ui/candidate-card'
import { fetchCatalog } from '@/fsd/entities/catalog/api/catalog-api'
import { fetchCandidates } from '@/fsd/entities/employer/api/employer-api'
import { InvitationForm } from '@/fsd/features/invitations/invitation-form'
import type { Grade } from '@/fsd/shared/api/types'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { Button } from '@/fsd/shared/ui/button'
import { EmptyState } from '@/fsd/shared/ui/empty-state'
import { Input } from '@/fsd/shared/ui/input'
import { Select } from '@/fsd/shared/ui/select'
import { Skeleton } from '@/fsd/shared/ui/skeleton'

const PAGE_SIZE = 24

/*
 * Candidate bank (PRD §7.3): the whole base with filters and pager in
 * URL-state (?spec&grade&stack&fsp&offset) — shareable, survives navigation.
 * Changing any filter resets the offset to the first page.
 */
export function CandidatesBank() {
  const router = useRouter()
  const params = useSearchParams()
  const spec = params.get('spec') ?? ''
  const grade = params.get('grade') ?? ''
  const stack = params.get('stack') ?? ''
  const fsp = params.get('fsp') === '1'
  const offset = Math.max(0, Number(params.get('offset') ?? '0') || 0)
  const [inviteTarget, setInviteTarget] = useState<{ candidateId: string; name: string } | null>(
    null,
  )

  const catalog = useQuery(() => fetchCatalog())
  const candidates = useQuery(
    () =>
      fetchCandidates({
        spec: spec || undefined,
        grade: (grade || undefined) as Grade | undefined,
        stack: stack || undefined,
        fsp: fsp || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    [spec, grade, stack, fsp, offset],
  )

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params.toString())
    if (value) next.set(key, value)
    else next.delete(key)
    next.delete('offset') // any filter change goes back to the first page
    router.replace(`?${next.toString()}`, { scroll: false })
  }

  function goTo(newOffset: number) {
    const next = new URLSearchParams(params.toString())
    if (newOffset > 0) next.set('offset', String(newOffset))
    else next.delete('offset')
    router.replace(`?${next.toString()}`, { scroll: false })
  }

  const shown = candidates.data?.length ?? 0
  const hasPrev = offset > 0
  const hasNext = shown === PAGE_SIZE

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-2 rounded-xl border border-border bg-card p-3 sm:grid-cols-2 lg:grid-cols-5">
        <Select
          value={spec}
          onChange={(e) => setParam('spec', e.target.value)}
          aria-label="Специализация"
        >
          <option value="">Все специализации</option>
          {(catalog.data?.specializations ?? []).map((s) => (
            <option key={s.slug} value={s.slug}>
              {s.title}
            </option>
          ))}
        </Select>
        <Select
          value={grade}
          onChange={(e) => setParam('grade', e.target.value)}
          aria-label="Грейд"
        >
          <option value="">Все грейды</option>
          {(catalog.data?.grades ?? []).map((g) => (
            <option key={g.slug} value={g.slug}>
              {g.title}
            </option>
          ))}
        </Select>
        <Input
          value={stack}
          onChange={(e) => setParam('stack', e.target.value)}
          placeholder="Стек: python, react…"
          aria-label="Стек"
        />
        <label className="flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-input bg-background px-2.5 text-sm">
          <input
            type="checkbox"
            checked={fsp}
            onChange={(e) => setParam('fsp', e.target.checked ? '1' : '')}
            className="size-4 accent-primary"
          />
          Есть достижения ФСП
        </label>
        <Button
          variant="ghost"
          onClick={() => router.replace('?', { scroll: false })}
          disabled={!spec && !grade && !stack && !fsp}
        >
          Сбросить
        </Button>
      </div>

      {candidates.loading && (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}
      {candidates.error && (
        <EmptyState
          icon={SearchXIcon}
          title="Не удалось загрузить банк"
          hint={candidates.error.message}
        />
      )}
      {candidates.data && candidates.data.length === 0 && (
        <EmptyState
          icon={SearchXIcon}
          title="Никого не найдено"
          hint="Попробуйте смягчить фильтры — база пополняется."
        />
      )}
      <div className="flex flex-col gap-3">
        {candidates.data?.map((candidate) => (
          <CandidateCard
            key={candidate.profile.candidate_id}
            candidate={candidate}
            onInvite={(candidateId, name) => setInviteTarget({ candidateId, name })}
          />
        ))}
      </div>

      {shown > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            Показано{' '}
            <span className="font-mono tabular-nums">
              {offset + 1}–{offset + shown}
            </span>
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={!hasPrev}
              onClick={() => goTo(offset - PAGE_SIZE)}
            >
              <ChevronLeftIcon />
              Назад
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!hasNext}
              onClick={() => goTo(offset + PAGE_SIZE)}
            >
              Вперёд
              <ChevronRightIcon />
            </Button>
          </div>
        </div>
      )}

      <InvitationForm
        target={inviteTarget}
        open={inviteTarget !== null}
        onOpenChange={(open) => !open && setInviteTarget(null)}
        onCreated={() => {}}
      />
    </div>
  )
}
