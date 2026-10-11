'use client'

import { useState } from 'react'

import type { ExplanationFactor, ShortlistItem } from '@/fsd/shared/api/types'
import { GRADE_LABELS, GRADE_STATUS_LABELS, SPEC_LABELS } from '@/fsd/shared/lib/format'
import { Badge } from '@/fsd/shared/ui/badge'
import { Button } from '@/fsd/shared/ui/button'
import { Card } from '@/fsd/shared/ui/card'

/** Weighted contribution bar of one explanation factor (§7.5.3). */
function FactorBar({ factor }: { factor: ExplanationFactor }) {
  const pct = Math.max(0, Math.min(100, factor.contribution * 100))
  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-4 text-sm">
        <span className="text-ink-2">{factor.human_text}</span>
        <span className="shrink-0 font-mono text-xs font-medium text-ink tabular-nums">
          +{factor.contribution.toFixed(2)}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-pill bg-background" role="presentation">
        <div
          className="h-full rounded-pill bg-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </li>
  )
}

/*
 * Shortlist candidate card (money screen §7.11.1): profile without contacts
 * + expandable «Почему в подборке» panel — score decomposition by factors
 * with weighted bars. «Пригласить» opens the invitation form (§7.6).
 */
export function ShortlistCard({
  item,
  defaultOpen = false,
  onInvite,
}: {
  item: ShortlistItem
  defaultOpen?: boolean
  onInvite?: (candidateId: string, name: string) => void
}) {
  const [open, setOpen] = useState(defaultOpen)
  const { profile, contacts } = item.candidate
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-heading">{profile.fio}</p>
          <p className="text-xs text-muted-foreground">
            {profile.spec_slug ? (SPEC_LABELS[profile.spec_slug] ?? profile.spec_slug) : '—'}
            {profile.grade_verified ? ` · ${GRADE_LABELS[profile.grade_verified]}` : ''}
            {profile.experience_years != null ? ` · стаж ${profile.experience_years} г.` : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {profile.grade_status === 'unverified' && (
            <Badge variant="outline">{GRADE_STATUS_LABELS.unverified}</Badge>
          )}
          {profile.has_fsp && <Badge variant="accent">ФСП</Badge>}
          <span className="font-mono text-lg font-semibold text-primary tabular-nums">
            {item.score.toFixed(2)}
          </span>
        </div>
      </div>

      <ul className="flex flex-wrap gap-1.5" aria-label="Стек">
        {profile.stack.map((tech) => (
          <li key={tech}>
            <Badge>{tech}</Badge>
          </li>
        ))}
      </ul>

      {contacts && (
        <div className="rounded-lg bg-success-soft p-3 font-mono text-sm text-ink-2">
          {contacts.email && <p>email: {contacts.email}</p>}
          {contacts.phone && <p>тел: {contacts.phone}</p>}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="cursor-pointer text-sm font-medium text-primary hover:underline"
        >
          {open ? 'Скрыть разбор' : 'Почему в подборке'}
        </button>
        {onInvite && (
          <Button
            size="sm"
            className="ml-auto"
            onClick={() => onInvite(profile.candidate_id, profile.fio)}
          >
            Пригласить
          </Button>
        )}
      </div>

      {open && (
        <ul className="flex flex-col gap-3 rounded-lg bg-muted p-3">
          {item.explanation.map((factor) => (
            <FactorBar key={factor.factor} factor={factor} />
          ))}
        </ul>
      )}
    </Card>
  )
}
