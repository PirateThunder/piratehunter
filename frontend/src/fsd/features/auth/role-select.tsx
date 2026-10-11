'use client'

import { BriefcaseIcon, UserRoundIcon } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { toast } from 'sonner'

import { selectRole } from '@/fsd/entities/session/api/auth-api'
import { useSession } from '@/fsd/entities/session/model/session-store'
import type { Role } from '@/fsd/shared/api/types'

import { ROLE_HOME } from './lib/routes'

/**
 * First-login role choice (PRD §7.1). Persisted on the backend via
 * POST /users/me/role; consent_pd (152-ФЗ) is mandatory, consent_publish
 * («показывать профиль работодателям») — a separate opt-in for candidates.
 */
export function RoleSelect() {
  const router = useRouter()
  const [consentPd, setConsentPd] = useState(false)
  const [consentPublish, setConsentPublish] = useState(false)
  const [pending, setPending] = useState(false)

  async function choose(role: Role) {
    if (pending) return
    setPending(true)
    try {
      const user = await selectRole(role, role === 'candidate' && consentPublish)
      useSession.getState().setUser(user)
      router.replace(ROLE_HOME[role])
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось сохранить роль')
      setPending(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-center text-sm text-muted-foreground">Кто вы на платформе?</p>
      <button
        type="button"
        onClick={() => void choose('candidate')}
        disabled={!consentPd || pending}
        className="flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        <UserRoundIcon className="size-6 shrink-0 text-primary" aria-hidden />
        <span>
          <span className="block font-medium text-heading">Я кандидат</span>
          <span className="block text-sm text-muted-foreground">
            Подтверждаю грейд тестом и получаю приглашения с вилкой
          </span>
        </span>
      </button>
      <button
        type="button"
        onClick={() => void choose('employer')}
        disabled={!consentPd || pending}
        className="flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        <BriefcaseIcon className="size-6 shrink-0 text-primary" aria-hidden />
        <span>
          <span className="block font-medium text-heading">Я работодатель</span>
          <span className="block text-sm text-muted-foreground">
            Описываю потребность и сам нахожу людей в базе
          </span>
        </span>
      </button>
      <div className="flex flex-col gap-2 text-xs text-muted-foreground">
        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="checkbox"
            checked={consentPd}
            onChange={(e) => setConsentPd(e.target.checked)}
            className="mt-0.5 size-4 accent-primary"
          />
          <span>Согласен на обработку персональных данных (152-ФЗ) — обязательно</span>
        </label>
        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="checkbox"
            checked={consentPublish}
            onChange={(e) => setConsentPublish(e.target.checked)}
            className="mt-0.5 size-4 accent-primary"
          />
          <span>Кандидатам: показывать профиль работодателям (можно изменить позже)</span>
        </label>
      </div>
    </div>
  )
}
