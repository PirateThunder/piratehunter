'use client'

import { useState } from 'react'
import { toast } from 'sonner'

import { linkFsp, putCandidateProfile, unlinkFsp } from '@/fsd/entities/candidate/api/candidate-api'
import type { CandidateSelf } from '@/fsd/shared/api/types'
import { Button } from '@/fsd/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/fsd/shared/ui/card'
import { Input } from '@/fsd/shared/ui/input'

/** Privacy toggles, consents and ФСП ID linking (PRD §7.2 «Настройки»). */
export function SettingsSection({
  profile,
  onSaved,
}: {
  profile: CandidateSelf
  onSaved: (p: CandidateSelf) => void
}) {
  const [privacy, setPrivacy] = useState(profile.privacy)
  const [fspId, setFspId] = useState(profile.fsp_id ?? '')
  const [pending, setPending] = useState(false)

  async function savePrivacy() {
    if (pending) return
    setPending(true)
    try {
      const saved = await putCandidateProfile({ fio: profile.fio, privacy })
      onSaved(saved)
      toast.success('Настройки приватности сохранены')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось сохранить настройки')
    } finally {
      setPending(false)
    }
  }

  async function link() {
    if (pending || !fspId.trim()) return
    setPending(true)
    try {
      const saved = await linkFsp(fspId.trim())
      onSaved(saved)
      toast.success('ФСП ID привязан')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось привязать ФСП ID')
    } finally {
      setPending(false)
    }
  }

  async function unlink() {
    if (pending) return
    setPending(true)
    try {
      const saved = await unlinkFsp()
      onSaved(saved)
      setFspId('')
      toast.success('ФСП ID отвязан')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось отвязать ФСП ID')
    } finally {
      setPending(false)
    }
  }

  const toggles = [
    {
      key: 'anonymous' as const,
      label: 'Анонимный режим «Кандидат #id»',
      hint: 'ФИО скрыто до принятия приглашения',
    },
    { key: 'show_stack' as const, label: 'Показывать стек', hint: 'технологии в карточке профиля' },
    {
      key: 'show_fsp' as const,
      label: 'Показывать достижения ФСП',
      hint: 'рейтинг, разряды, дипломы',
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Приватность</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-xs text-muted-foreground">
            Контактные данные скрыты всегда до принятия приглашения — это правило платформы, а не
            настройка (ТЗ §2.2). Анонимность — ваш выбор (Q&A 07.10).
          </p>
          {toggles.map(({ key, label, hint }) => (
            <label key={key} className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={privacy[key]}
                onChange={(e) => setPrivacy({ ...privacy, [key]: e.target.checked })}
                className="mt-0.5 size-4 accent-primary"
              />
              <span>
                <span className="block text-sm font-medium text-ink-2">{label}</span>
                <span className="block text-xs text-muted-foreground">{hint}</span>
              </span>
            </label>
          ))}
          <Button onClick={() => void savePrivacy()} disabled={pending} className="self-start">
            {pending ? 'Сохраняем…' : 'Сохранить'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Привязка ФСП ID</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            Автоматически привязывается при входе через FSP ID; вручную — по идентификатору.
          </p>
          <div className="flex flex-wrap gap-2">
            <Input
              value={fspId}
              onChange={(e) => setFspId(e.target.value)}
              placeholder="FSP-…"
              className="max-w-56 font-mono"
              aria-label="ФСП ID"
            />
            {profile.fsp_id ? (
              <Button variant="outline" onClick={() => void unlink()} disabled={pending}>
                Отвязать {profile.fsp_id}
              </Button>
            ) : (
              <Button onClick={() => void link()} disabled={pending || !fspId.trim()}>
                Привязать
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
