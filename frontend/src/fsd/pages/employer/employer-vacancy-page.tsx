'use client'

import { ArrowLeftIcon } from 'lucide-react'
import Link from 'next/link'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'

import { fetchCatalog } from '@/fsd/entities/catalog/api/catalog-api'
import {
  closeVacancy,
  patchApplicationStatus,
  publishVacancy,
  updateVacancy,
} from '@/fsd/entities/employer/api/employer-api'
import { RoleGate } from '@/fsd/features/auth/role-gate'
import { cabinetApi } from '@/fsd/shared/api/cabinet-api'
import type { ApplicationEmployer, Grade, SalaryType, SpecSlug } from '@/fsd/shared/api/types'
import { formatDate, formatSalary, gradeLabel } from '@/fsd/shared/lib/format'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { Badge } from '@/fsd/shared/ui/badge'
import { Button } from '@/fsd/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/fsd/shared/ui/card'
import { EmptyState } from '@/fsd/shared/ui/empty-state'
import { Field } from '@/fsd/shared/ui/field'
import { Input } from '@/fsd/shared/ui/input'
import { Select } from '@/fsd/shared/ui/select'
import { Skeleton } from '@/fsd/shared/ui/skeleton'
import { Textarea } from '@/fsd/shared/ui/textarea'

const STATUS_LABELS = { draft: 'Черновик', published: 'Опубликована', closed: 'Закрыта' } as const
const APP_LABELS = {
  sent: 'Отправлен',
  viewed: 'Просмотрен',
  invited: 'Приглашён',
  rejected: 'Отклонён',
} as const

/** Vacancy editor + incoming applications (PRD §7.7). */
export function EmployerVacancyPage({ vacancyId }: { vacancyId: string }) {
  return (
    <RoleGate allowedRole="employer">
      <VacancyCabinet vacancyId={vacancyId} />
    </RoleGate>
  )
}

function VacancyCabinet({ vacancyId }: { vacancyId: string }) {
  const [reload, setReload] = useState(0)
  const catalog = useQuery(() => fetchCatalog())
  const vacancy = useQuery(() => cabinetApi.employer.getVacancy(vacancyId), [vacancyId, reload])
  const applications = useQuery(
    () => cabinetApi.employer.getVacancyApplications(vacancyId),
    [vacancyId, reload],
  )

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [spec, setSpec] = useState<SpecSlug | ''>('')
  const [grade, setGrade] = useState<Grade | ''>('')
  const [stack, setStack] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [salaryType, setSalaryType] = useState<SalaryType>('gross')
  const [pending, setPending] = useState(false)
  const [prefilled, setPrefilled] = useState(false)

  const v = vacancy.data
  if (v && !prefilled) {
    setTitle(v.title)
    setDescription(v.description)
    setSpec(v.spec_slug ?? '')
    setGrade(v.grade ?? '')
    setStack(v.stack_must.join(', '))
    setFrom(String(v.salary_from))
    setTo(String(v.salary_to))
    setSalaryType(v.salary_type)
    setPrefilled(true)
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    const salaryFrom = Number(from)
    const salaryTo = Number(to)
    if (!salaryFrom || !salaryTo || salaryFrom > salaryTo) {
      toast.error('Проверьте вилку: от ≤ до, оба заполнены')
      return
    }
    setPending(true)
    try {
      await updateVacancy(vacancyId, {
        title: title.trim(),
        description: description.trim(),
        spec_slug: spec || null,
        grade: grade || null,
        stack_must: stack
          .split(',')
          .map((s) => s.trim().toLowerCase())
          .filter(Boolean),
        salary_from: salaryFrom,
        salary_to: salaryTo,
        salary_type: salaryType,
      })
      toast.success('Вакансия сохранена')
      setReload((n) => n + 1)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось сохранить')
    } finally {
      setPending(false)
    }
  }

  async function toggleStatus(action: 'publish' | 'close') {
    try {
      await (action === 'publish' ? publishVacancy(vacancyId) : closeVacancy(vacancyId))
      setReload((n) => n + 1)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось изменить статус')
    }
  }

  async function setAppStatus(id: string, status: 'viewed' | 'invited' | 'rejected') {
    try {
      await patchApplicationStatus(id, status)
      toast.success('Статус отклика обновлён')
      setReload((n) => n + 1)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось обновить отклик')
    }
  }

  if (!v) return <Skeleton className="h-64 w-full" />

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/employer/vacancies" aria-label="К списку вакансий">
            <Button variant="ghost">
              <ArrowLeftIcon />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-heading">{v.title}</h1>
            <p className="text-sm text-muted-foreground">
              <Badge variant={v.status === 'published' ? 'success' : 'outline'}>
                {STATUS_LABELS[v.status]}
              </Badge>{' '}
              · {formatSalary(v.salary_from, v.salary_to)} ({v.salary_type})
            </p>
          </div>
        </div>
        {v.status !== 'published' ? (
          <Button onClick={() => void toggleStatus('publish')}>Опубликовать</Button>
        ) : (
          <Button variant="outline" onClick={() => void toggleStatus('close')}>
            Закрыть
          </Button>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Редактор</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={(e) => void save(e)} className="flex flex-col gap-4">
              <Field label="Заголовок">
                {(id) => (
                  <Input
                    id={id}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
                  />
                )}
              </Field>
              <Field label="Описание">
                {(id) => (
                  <Textarea
                    id={id}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="min-h-24"
                    required
                  />
                )}
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Специализация">
                  {(id) => (
                    <Select
                      id={id}
                      value={spec}
                      onChange={(e) => setSpec(e.target.value as SpecSlug | '')}
                    >
                      <option value="">—</option>
                      {catalog.data?.specializations.map((s) => (
                        <option key={s.slug} value={s.slug}>
                          {s.title}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <Field label="Грейд">
                  {(id) => (
                    <Select
                      id={id}
                      value={grade}
                      onChange={(e) => setGrade(e.target.value as Grade | '')}
                    >
                      <option value="">—</option>
                      {catalog.data?.grades.map((g) => (
                        <option key={g.slug} value={g.slug}>
                          {g.title}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              </div>
              <Field label="Стек (через запятую)">
                {(id) => <Input id={id} value={stack} onChange={(e) => setStack(e.target.value)} />}
              </Field>
              <div className="grid grid-cols-3 gap-3">
                <Field label="От, ₽">
                  {(id) => (
                    <Input
                      id={id}
                      type="number"
                      min={0}
                      step={5000}
                      value={from}
                      onChange={(e) => setFrom(e.target.value)}
                    />
                  )}
                </Field>
                <Field label="До, ₽">
                  {(id) => (
                    <Input
                      id={id}
                      type="number"
                      min={0}
                      step={5000}
                      value={to}
                      onChange={(e) => setTo(e.target.value)}
                    />
                  )}
                </Field>
                <Field label="Тип">
                  {(id) => (
                    <Select
                      id={id}
                      value={salaryType}
                      onChange={(e) => setSalaryType(e.target.value as SalaryType)}
                    >
                      <option value="gross">gross</option>
                      <option value="net">net</option>
                    </Select>
                  )}
                </Field>
              </div>
              <Button type="submit" disabled={pending}>
                {pending ? 'Сохраняем…' : 'Сохранить'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Входящие отклики {applications.data ? `(${applications.data.length})` : ''}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {applications.data?.length === 0 && (
              <EmptyState
                icon={ArrowLeftIcon}
                title="Откликов пока нет"
                hint="Опубликованная вакансия видна кандидатам, они могут откликнуться сами."
              />
            )}
            {applications.data?.map((a) => (
              <ApplicationRow
                key={a.id}
                application={a}
                onStatus={setAppStatus}
                catalog={catalog.data ?? null}
              />
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function ApplicationRow({
  application,
  onStatus,
  catalog,
}: {
  application: ApplicationEmployer
  onStatus: (id: string, status: 'viewed' | 'invited' | 'rejected') => void
  catalog: Parameters<typeof gradeLabel>[0]
}) {
  const p = application.candidate.profile
  const contacts = application.candidate.contacts?.contacts ?? {}
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{p.fio}</span>
        <Badge variant={application.status === 'invited' ? 'success' : 'outline'}>
          {APP_LABELS[application.status]}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        {p.grade_verified
          ? `подтверждён: ${gradeLabel(catalog, p.grade_verified)}`
          : 'грейд не подтверждён'}
        {p.stack.length ? ` · ${p.stack.slice(0, 5).join(', ')}` : ''}
      </p>
      {application.message && <p className="mt-1 text-sm text-ink-2">{application.message}</p>}
      <p className="mt-1 text-xs text-muted-foreground">
        Контакты (кандидат откликнулся сам):{' '}
        {Object.values(contacts).filter(Boolean).join(' · ') || 'не указаны'} ·{' '}
        {formatDate(application.created_at)}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button variant="secondary" onClick={() => onStatus(application.id, 'invited')}>
          Пригласить
        </Button>
        <Button variant="outline" onClick={() => onStatus(application.id, 'rejected')}>
          Отклонить
        </Button>
      </div>
    </div>
  )
}
