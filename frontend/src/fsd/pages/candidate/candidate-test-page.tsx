'use client'

import { RoleGate } from '@/fsd/features/auth/role-gate'
import { TestFlow } from '@/fsd/features/test/test-flow'

/** Adaptive test page (money screen §7.11.2) — separate full-focus route. */
export function CandidateTestPage() {
  return (
    <RoleGate allowedRole="candidate">
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold text-heading">Тест на грейд</h1>
          <p className="text-sm text-muted-foreground">
            Адаптивные вопросы по вашей специализации, таймер на вопрос
          </p>
        </div>
        <TestFlow />
      </div>
    </RoleGate>
  )
}
