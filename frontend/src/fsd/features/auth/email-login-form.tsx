'use client'

import { MailIcon } from 'lucide-react'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { authEmailRequest, authEmailVerify } from '@/fsd/entities/session/api/auth-api'
import { useSession } from '@/fsd/entities/session/model/session-store'
import type { User } from '@/fsd/entities/session/model/types'
import { Button } from '@/fsd/shared/ui/button'
import { Input } from '@/fsd/shared/ui/input'

const RESEND_COOLDOWN = 60

/**
 * Email sign-in (PRD §7.1): address → 6-digit code → token pair. New accounts
 * are created on first verify; the 152-ФЗ consent checkboxes (ТЗ §2.2.4) gate
 * the code request. `onDone` receives the user so the page can route by role.
 */
export function EmailLoginForm({ onDone }: { onDone: (user: User) => void }) {
  const [step, setStep] = useState<'email' | 'code'>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [consentPd, setConsentPd] = useState(false)
  const [consentPublish, setConsentPublish] = useState(false)
  const [pending, setPending] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current)
    },
    [],
  )

  const startCooldown = () => {
    setCooldown(RESEND_COOLDOWN)
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setCooldown((left) => {
        if (left <= 1 && timerRef.current) clearInterval(timerRef.current)
        return Math.max(0, left - 1)
      })
    }, 1000)
  }

  const requestCode = async (event: FormEvent) => {
    event.preventDefault()
    const trimmed = email.trim()
    if (!trimmed || pending) return
    setPending(true)
    try {
      await authEmailRequest(trimmed)
      setEmail(trimmed)
      setStep('code')
      startCooldown()
      toast.success('Код отправлен — проверьте почту')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось отправить код')
    } finally {
      setPending(false)
    }
  }

  const verify = async (event: FormEvent) => {
    event.preventDefault()
    const trimmed = code.trim()
    if (trimmed.length !== 6 || pending) return
    setPending(true)
    try {
      const data = await authEmailVerify(email, trimmed)
      useSession.getState().setSession(data.user, data.access_token, data.expires_in)
      onDone(data.user)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Неверный код')
      setPending(false)
    }
  }

  if (step === 'code') {
    return (
      <form onSubmit={(e) => void verify(e)} className="flex flex-col gap-2">
        <label htmlFor="email-code" className="text-xs text-muted-foreground">
          Код из письма на {email}
        </label>
        <Input
          id="email-code"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="123456"
          inputMode="numeric"
          autoComplete="one-time-code"
          autoFocus
          className="text-center font-mono text-lg tracking-[0.5em]"
        />
        <Button type="submit" disabled={pending || code.length !== 6}>
          {pending ? 'Проверяем…' : 'Войти'}
        </Button>
        <div className="flex justify-between text-xs">
          <button
            type="button"
            onClick={() => {
              setStep('email')
              setCode('')
            }}
            className="cursor-pointer text-muted-foreground underline hover:text-foreground"
          >
            Изменить почту
          </button>
          <button
            type="button"
            disabled={cooldown > 0 || pending}
            onClick={(e) => void requestCode(e)}
            className="cursor-pointer text-muted-foreground underline hover:text-foreground disabled:no-underline disabled:opacity-60"
          >
            {cooldown > 0 ? `Отправить снова (${cooldown})` : 'Отправить снова'}
          </button>
        </div>
      </form>
    )
  }

  return (
    <form onSubmit={(e) => void requestCode(e)} className="flex flex-col gap-3">
      <label htmlFor="email-login" className="text-xs text-muted-foreground">
        Или по почте — пришлём код для входа
      </label>
      <div className="flex gap-2">
        <Input
          id="email-login"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          autoComplete="email"
          maxLength={320}
        />
        <Button type="submit" variant="secondary" disabled={pending || !consentPd || !email.trim()}>
          <MailIcon />
          {pending ? 'Шлём…' : 'Код'}
        </Button>
      </div>
      <div className="flex flex-col gap-2 text-xs text-muted-foreground">
        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="checkbox"
            checked={consentPd}
            onChange={(e) => setConsentPd(e.target.checked)}
            className="mt-0.5 size-4 accent-primary"
          />
          <span>Согласен на обработку персональных данных (152-ФЗ)</span>
        </label>
        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="checkbox"
            checked={consentPublish}
            onChange={(e) => setConsentPublish(e.target.checked)}
            className="mt-0.5 size-4 accent-primary"
          />
          <span>Согласен на показ профиля работодателям (можно изменить позже)</span>
        </label>
      </div>
    </form>
  )
}
