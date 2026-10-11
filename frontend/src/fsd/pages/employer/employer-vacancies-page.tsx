'use client'

import { BriefcaseIcon } from 'lucide-react'
import Link from 'next/link'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'

import { fetchCatalog } from '@/fsd/entities/catalog/api/catalog-api'
import {
  closeVacancy,
  createVacancy,
  publishVacancy,
} from '@/fsd/entities/employer/api/employer-api'
import { RoleGate } from '@/fsd/features/auth/role-gate'
import { cabinetApi } from '@/fsd/shared/api/cabinet-api'
import type { Grade, SalaryType, SpecSlug } from '@/fsd/shared/api/types'
import { formatDate, formatSalary } from '@/fsd/shared/lib/format'
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
import { Input } from '@/fsd/shared/ui/input'
import { Select } from '@/fsd/shared/ui/select'
import { Skeleton } from '@/fsd/shared/ui/skeleton'
import { Textarea } from '@/fsd/shared/ui/textarea'

const STATUS_LABELS = { draft: 'Черновик', published: 'Опубликована', closed: 'Закрыта' } as const

/** Employer vacancies CRUD (PRD §7.7). */
export function EmployerVacanciesPage() {
  return (
    <RoleGate allowedRole="employer">
      <VacanciesCabinet />
    </RoleGate>
  )
}

function VacanciesCabinet() {
  const [reload, setReload] = useState(0)
  const [open, setOpen] = useState(false)
  const catalog = useQuery(() => fetchCatalog())
  const vacancies = useQuery(() => cabinetApi.employer.getVacancies(), [reload])

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [spec, setSpec] = useState<SpecSlug | ''>('')
  const [grade, setGrade] = useState<Grade | ''>('')
  const [stack, setStack] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [salaryType, setSalaryType] = useState<SalaryType>('gross')
  const [pending, setPending] = useState(false)

  async function create(e: FormEvent) {
    e.preventDefault()
    const salaryFrom = Number(from)
    const salaryTo = Number(to)
    if (!salaryFrom || !salaryTo) {
      toast.error('Зарплатная вилка обязательна (ТЗ §2.2)')
      return
    }
    if (salaryFrom > salaryTo) {
      toast.error('Вилка: «от» больше «до»')
      return
    }
    setPending(true)
    try {
      await createVacancy({
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
      toast.success('Вакансия создана — черновик можно опубликовать')
      setOpen(false)
      setTitle('')
      setDescription('')
      setSpec('')
      setGrade('')
      setStack('')
      setFrom('')
      setTo('')
      setReload((n) => n + 1)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось создать вакансию')
    } finally {
      setPending(false)
    }
  }

  async function toggleStatus(id: string, action: 'publish' | 'close') {
    try {
      await (action === 'publish' ? publishVacancy(id) : closeVacancy(id))
      toast.success(action === 'publish' ? 'Вакансия опубликована' : 'Вакансия закрыта')
      setReload((n) => n + 1)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось изменить статус')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-heading">Вакансии</h1>
          <p className="text-sm text-muted-foreground">
            Публикация открывает кандидатам самостоятельный отклик (§7.7); вилка обязательна
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>Новая вакансия</Button>
      </div>

      {vacancies.loading && <Skeleton className="h-40 w-full" />}
      {vacancies.data?.length === 0 && (
        <EmptyState
          icon={BriefcaseIcon}
          title="Вакансий пока нет"
          hint="Опишите позицию — кандидаты увидят её в списке открытых и смогут откликнуться сами."
        />
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {vacancies.data?.map((v) => (
          <Card key={v.id}>
            <CardHeader className="gap-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="text-base">{v.title}</CardTitle>
                <Badge variant={v.status === 'published' ? 'success' : 'outline'}>
                  {STATUS_LABELS[v.status]}
                </Badge>
              </div>
              <p className="font-mono text-sm text-ink-2">
                {formatSalary(v.salary_from, v.salary_to)}
              </p>
              <p className="text-xs text-muted-foreground">создана {formatDate(v.created_at)}</p>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Link href={`/employer/vacancies/${v.id}`}>
                <Button variant="secondary">Открыть</Button>
              </Link>
              {v.status !== 'published' ? (
                <Button variant="outline" onClick={() => void toggleStatus(v.id, 'publish')}>
                  Опубликовать
                </Button>
              ) : (
                <Button variant="outline" onClick={() => void toggleStatus(v.id, 'close')}>
                  Закрыть
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Новая вакансия</DialogTitle>
            <DialogDescription>
              Кандидаты увидят вилку и стек; отклики придут с открытыми контактами.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={(e) => void create(e)} className="flex flex-col gap-4">
            <Field label="Заголовок">
              {(id) => (
                <Input
                  id={id}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                  maxLength={300}
                />
              )}
            </Field>
            <Field label="Описание">
              {(id) => (
                <Textarea
                  id={id}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required
                  className="min-h-24"
                  maxLength={10000}
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
              {(id) => (
                <Input
                  id={id}
                  value={stack}
                  onChange={(e) => setStack(e.target.value)}
                  placeholder="python, fastapi, postgresql"
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
            <DialogFooter>
              <Button type="submit" disabled={pending}>
                {pending ? 'Создаём…' : 'Создать черновик'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
