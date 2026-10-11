'use client'

import { useRouter } from 'next/navigation'

import { RoleGate } from '@/fsd/features/auth/role-gate'
import { NeedEditor } from '@/fsd/features/needs/need-editor'

/** New need: free text → parse → structure → save → shortlist page. */
export function EmployerNewNeedPage() {
  const router = useRouter()
  return (
    <RoleGate allowedRole="employer">
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-bold text-heading">Новая потребность</h1>
        <NeedEditor onSaved={(need) => router.push(`/employer/needs/${need.id}`)} />
      </div>
    </RoleGate>
  )
}
