'use client'

import { BriefcaseIcon } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'

import { fetchCatalog } from '@/fsd/entities/catalog/api/catalog-api'
import { applyToVacancy, fetchPublicVacancies } from '@/fsd/entities/vacancy/api/vacancy-api'
import type { Grade, SpecSlug, VacancyPublic } from '@/fsd/shared/api/types'
import { gradeLabel, specLabel } from '@/fsd/shared/lib/format'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { Badge } from '@/fsd/shared/ui/badge'
import { Button } from '@/fsd/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/fsd/shared/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/fsd/shared/ui/dialog'
import { EmptyState } from '@/fsd/shared/ui/empty-state'
import { Field } from '@/fsd/shared/ui/field'
import { SalaryRange } from '@/fsd/shared/ui/salary-range'
import { Select } from '@/fsd/shared/ui/select'
import { Skeleton } from '@/fsd/shared/ui/skeleton'
import { Textarea } from '@/fsd/shared/ui/textarea'

/**
 * Open vacancies for candidates (PRD §7.7): while there are no incoming
 * invitations, the candidate can show initiative and apply directly.
 */
export function VacanciesSection() {
  const [spec, setSpec] = useState<SpecSlug | ''>('')
  const [grade, setGrade] = useState<Grade | ''>('')
  const [target, setTarget] = useState<VacancyPublic | null>(null)
  const [message, setMessage] = useState('')
  const [pending, setPending] = useState(false)
  const [reload, setReload] = useState(0)

  const catalog = useQuery(() => fetchCatalog())
  const vacancies = useQuery(
    () =>
      fetchPublicVacancies({
        spec: spec || undefined,
        grade: grade || undefined,
        limit: 50,
      }),
    [spec, grade, reload],
  )

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (pending || !target) return
    setPending(true)
    try {
      await applyToVacancy(target.id, message.trim())
      toast.success('Отклик отправлен — работодатель увидит ваш профиль')
      setTarget(null)
      setMessage('')
      setReload((n) => n + 1)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось откликнуться')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Пока приглашений нет — можно проявить инициативу: отклик открывает работодателю ваш
        подтверждённый профиль.
      </p>
      <div className="flex flex-wrap gap-3">
        <Select
          aria-label="Специализация"
          className="max-w-56"
          value={spec}
          onChange={(e) => setSpec(e.target.value as SpecSlug | '')}
        >
          <option value="">Все специализации</option>
          {catalog.data?.specializations.map((s) => (
            <option key={s.slug} value={s.slug}>
              {s.title}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Грейд"
          className="max-w-40"
          value={grade}
          onChange={(e) => setGrade(e.target.value as Grade | '')}
        >
          <option value="">любой грейд</option>
          {catalog.data?.grades.map((g) => (
            <option key={g.slug} value={g.slug}>
              {g.title}
            </option>
          ))}
        </Select>
      </div>

      {vacancies.loading && <Skeleton className="h-40 w-full" />}
      {vacancies.data?.length === 0 && (
        <EmptyState
          icon={BriefcaseIcon}
          title="Нет открытых вакансий"
          hint="Попробуйте снять фильтры — работодатели публикуют вакансии с обязательной вилкой зарплаты."
        />
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {vacancies.data?.map((v) => (
          <Card key={v.id}>
            <CardHeader className="gap-1">
              <CardTitle className="text-base">{v.title}</CardTitle>
              <p className="text-sm text-muted-foreground">
                {v.company.name}
                {v.spec_slug ? ` · ${specLabel(catalog.data ?? null, v.spec_slug)}` : ''}
                {v.grade ? ` · ${gradeLabel(catalog.data ?? null, v.grade)}` : ''}
              </p>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <SalaryRange from={v.salary_from} to={v.salary_to} type={v.salary_type} />
              <div className="flex flex-wrap gap-1.5">
                {v.stack_must.map((s) => (
                  <Badge key={s} variant="outline">
                    {s}
                  </Badge>
                ))}
              </div>
              <p className="text-sm text-ink-2 line-clamp-3">{v.description}</p>
              {v.already_applied ? (
                <Badge variant="success" className="self-start">
                  Вы откликнулись
                </Badge>
              ) : (
                <Button className="self-start" onClick={() => setTarget(v)}>
                  Откликнуться
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={target !== null} onOpenChange={(open) => !open && setTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Отклик: {target?.title}</DialogTitle>
            <DialogDescription>
              Работодатель увидит ваш профиль и контакты — вы сами инициировали контакт.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
            <Field label="Сопроводительное сообщение">
              {(id) => (
                <Textarea
                  id={id}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  maxLength={4000}
                  className="min-h-24"
                  placeholder="Коротко: почему вам интересна вакансия"
                />
              )}
            </Field>
            <DialogFooter>
              <Button type="submit" disabled={pending}>
                {pending ? 'Отправляем…' : 'Отправить отклик'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
