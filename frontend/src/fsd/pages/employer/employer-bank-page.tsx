'use client'

import { Suspense } from 'react'

import { RoleGate } from '@/fsd/features/auth/role-gate'
import { Skeleton } from '@/fsd/shared/ui/skeleton'
import { CandidatesBank } from '@/fsd/widgets/employer/candidates-bank'

/** Candidate bank with URL-state filters (PRD §7.3). */
export function EmployerBankPage() {
  return (
    <RoleGate allowedRole="employer">
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold text-heading">Банк кандидатов</h1>
          <p className="text-sm text-muted-foreground">
            Вся база: фильтры по специализации, грейду, стеку и достижениям ФСП
          </p>
        </div>
        {/* useSearchParams inside CandidatesBank requires a Suspense boundary */}
        <Suspense fallback={<Skeleton className="h-40 w-full" />}>
          <CandidatesBank />
        </Suspense>
      </div>
    </RoleGate>
  )
}
