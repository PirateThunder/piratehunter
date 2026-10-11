'use client'

import { type FormEvent, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { createInvitation } from '@/fsd/entities/employer/api/employer-api'
import type { InvitationEmployer, Need, SalaryType } from '@/fsd/shared/api/types'
import { Button } from '@/fsd/shared/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/fsd/shared/ui/dialog'
import { Field } from '@/fsd/shared/ui/field'
import { Input } from '@/fsd/shared/ui/input'
import { Select } from '@/fsd/shared/ui/select'
import { Textarea } from '@/fsd/shared/ui/textarea'
import { SalaryMarketWidget } from '@/fsd/widgets/employer/salary-market-widget'

/*
 * Invitation form (PRD §7.6): text + mandatory salary range (validated,
 * type labeled gross/net) + contact method; vacancy binding optional.
 * Opened from a shortlist/bank candidate card.
 */
export function InvitationForm({
  target,
  need,
  open,
  onOpenChange,
  onCreated,
}: {
  target: { candidateId: string; name: string } | null
  need?: Need | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (invitation: InvitationEmployer) => void
}) {
  const [text, setText] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [salaryType, setSalaryType] = useState<SalaryType>('gross')
  const [contact, setContact] = useState('telegram')
  const [pending, setPending] = useState(false)

  // Prefill from the need whenever a new target opens the dialog (the
  // controlled Dialog doesn't fire onOpenChange for programmatic opens).
  useEffect(() => {
    if (!open) return
    setText('')
    setFrom(need?.salary_from != null ? String(need.salary_from) : '')
    setTo(need?.salary_to != null ? String(need.salary_to) : '')
    setSalaryType('gross')
    setContact('telegram')
  }, [open, need])

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (pending || !target) return
    const salaryFrom = Number(from)
    const salaryTo = Number(to)
    if (!salaryFrom || !salaryTo || salaryFrom <= 0) {
      toast.error('Зарплатная вилка обязательна (ТЗ §2.2)')
      return
    }
    if (salaryFrom > salaryTo) {
      toast.error('Вилка: «от» больше «до»')
      return
    }
    setPending(true)
    try {
      const invitation = await createInvitation({
        candidate_id: target.candidateId,
        text: text.trim(),
        salary_from: salaryFrom,
        salary_to: salaryTo,
        salary_type: salaryType,
        contact_method: contact.trim(),
      })
      onCreated(invitation)
      onOpenChange(false)
      toast.success('Приглашение отправлено')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось отправить приглашение')
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Приглашение: {target?.name}</DialogTitle>
          <DialogDescription>
            Кандидат увидит текст и вилку до ответа; ваши контакты раскроются после принятия.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
          <Field label="Текст приглашения">
            {(id) => (
              <Textarea
                id={id}
                value={text}
                onChange={(e) => setText(e.target.value)}
                required
                maxLength={10000}
                className="min-h-24"
                placeholder="Здравствуйте! Увидели ваш подтверждённый профиль…"
              />
            )}
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Вилка от, ₽ *">
              {(id) => (
                <Input
                  id={id}
                  type="number"
                  min={0}
                  step={5000}
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                  required
                />
              )}
            </Field>
            <Field label="Вилка до, ₽ *">
              {(id) => (
                <Input
                  id={id}
                  type="number"
                  min={0}
                  step={5000}
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                  required
                />
              )}
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Тип вилки">
              {(id) => (
                <Select
                  id={id}
                  value={salaryType}
                  onChange={(e) => setSalaryType(e.target.value as SalaryType)}
                >
                  <option value="gross">до вычета налогов (gross)</option>
                  <option value="net">на руки (net)</option>
                </Select>
              )}
            </Field>
            <Field label="Способ связи">
              {(id) => (
                <Input
                  id={id}
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  required
                  maxLength={300}
                  placeholder="telegram"
                />
              )}
            </Field>
          </div>

          {need?.spec_slug && need.grade && (
            <SalaryMarketWidget
              spec={need.spec_slug}
              grade={need.grade}
              from={from ? Number(from) : null}
              to={to ? Number(to) : null}
            />
          )}

          <DialogFooter>
            <Button type="submit" disabled={pending}>
              {pending ? 'Отправляем…' : 'Отправить приглашение'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
