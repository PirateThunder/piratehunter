'use client'

import Link from 'next/link'
import { use, useState } from 'react'

import { RoleGate } from '@/fsd/features/auth/role-gate'
import { NeedEditor } from '@/fsd/features/needs/need-editor'
import { cabinetApi } from '@/fsd/shared/api/cabinet-api'
import type { Need } from '@/fsd/shared/api/types'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { Skeleton } from '@/fsd/shared/ui/skeleton'
import { ShortlistPanel } from '@/fsd/widgets/employer/shortlist-panel'

/** Need page: editor on top, ranked shortlist with explanations below. */
export function EmployerNeedPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return (
    <RoleGate allowedRole="employer">
      <NeedView needId={id} />
    </RoleGate>
  )
}

function NeedView({ needId }: { needId: string }) {
  const [need, setNeed] = useState<Need | null>(null)
  useQuery(async () => {
    const found = await cabinetApi.employer.getNeed(needId)
    setNeed(found)
    return found
  }, [needId])

  if (!need) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <Link href="/employer" className="text-sm text-muted-foreground hover:text-foreground">
          ← Кабинет
        </Link>
        <h1 className="text-2xl font-bold text-heading">Потребность и подборка</h1>
      </div>
      <NeedEditor need={need} onSaved={setNeed} />
      <section className="flex flex-col gap-3" aria-labelledby="shortlist-heading">
        <h2 id="shortlist-heading" className="text-lg font-semibold text-heading">
          Подборка по потребности
        </h2>
        <ShortlistPanel need={need} />
      </section>
    </div>
  )
}
