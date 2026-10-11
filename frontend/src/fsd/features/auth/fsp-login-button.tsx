'use client'

import { ShieldCheckIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { fetchFspAuthorizeUrl } from '@/fsd/entities/session/api/auth-api'
import { cn } from '@/fsd/shared/lib/utils'

/**
 * «Войти через FSP ID» — the expected sign-in scenario (PRD §7.1): the
 * backend builds the mock-OIDC authorize URL, the browser redirects there;
 * after confirmation the backend lands back on /login/callback with the
 * refresh cookie set.
 */
export function FspLoginButton({ className }: { className?: string }) {
  const [pending, setPending] = useState(false)

  async function login() {
    if (pending) return
    setPending(true)
    try {
      const { authorize_url } = await fetchFspAuthorizeUrl()
      window.location.assign(authorize_url)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'FSP ID временно недоступен')
      setPending(false)
    }
  }

  return (
    <button
      type="button"
      onClick={() => void login()}
      disabled={pending}
      className={cn(
        'inline-flex h-9 w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-ink px-4 text-sm font-medium text-background transition-colors hover:bg-ink-2 disabled:opacity-50',
        className,
      )}
    >
      <ShieldCheckIcon className="size-4" aria-hidden />
      {pending ? 'Переходим к FSP ID…' : 'Войти через FSP ID'}
    </button>
  )
}
