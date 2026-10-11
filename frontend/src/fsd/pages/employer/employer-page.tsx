'use client'

import { Building2Icon, MailPlusIcon } from 'lucide-react'
import Link from 'next/link'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'
import { putCompany } from '@/fsd/entities/employer/api/employer-api'
import { InvitationTrackerCard } from '@/fsd/entities/invitation/ui/invitation-tracker-card'
import { RoleGate } from '@/fsd/features/auth/role-gate'
import { cabinetApi } from '@/fsd/shared/api/cabinet-api'
import type { CompanySelf, Need } from '@/fsd/shared/api/types'
import { formatDate, formatSalary, GRADE_LABELS, SPEC_LABELS } from '@/fsd/shared/lib/format'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { Badge } from '@/fsd/shared/ui/badge'
import { Button } from '@/fsd/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/fsd/shared/ui/card'
import { EmptyState } from '@/fsd/shared/ui/empty-state'
import { Input } from '@/fsd/shared/ui/input'
import { Skeleton } from '@/fsd/shared/ui/skeleton'
import { Textarea } from '@/fsd/shared/ui/textarea'
import { VacanciesSection } from '@/fsd/widgets/employer/vacancies-section'

/** Employer dashboard (PRD §7.3): needs, invitation tracker, company profile. */
export function EmployerPage() {
  return (
    <RoleGate allowedRole="employer">
      <EmployerDashboard />
    </RoleGate>
  )
}

function EmployerDashboard() {
  const needs = useQuery(() => cabinetApi.employer.getNeeds())
  const invitations = useQuery(() => cabinetApi.employer.getInvitations())
  const company = useQuery(() => cabinetApi.employer.getCompany())
  const vacancies = useQuery(() => cabinetApi.employer.getVacancies())

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-heading">Кабинет работодателя</h1>
          <p className="text-sm text-muted-foreground">
            Потребности, подборка с объяснением, приглашения
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/employer/bank">
            <Button variant="outline">Банк кандидатов</Button>
          </Link>
          <Link href="/employer/needs/new">
            <Button>Новая потребность</Button>
          </Link>
        </div>
      </div>

      <section className="flex flex-col gap-3" aria-labelledby="needs-heading">
        <h2 id="needs-heading" className="text-lg font-semibold text-heading">
          Потребности
        </h2>
        {needs.loading && <Skeleton className="h-28 w-full" />}
        {needs.data?.length === 0 && (
          <EmptyState
            icon={Building2Icon}
            title="Нет потребностей"
            hint="Опишите свободным текстом, кого ищете — система разберёт в структуру и соберёт подборку."
            action={
              <Link href="/employer/needs/new">
                <Button>Создать потребность</Button>
              </Link>
            }
          />
        )}
        <div className="grid gap-3 md:grid-cols-2">
          {needs.data?.map((need) => (
            <NeedCard key={need.id} need={need} />
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="tracker-heading">
        <h2 id="tracker-heading" className="text-lg font-semibold text-heading">
          Трекер приглашений
        </h2>
        {invitations.loading && <Skeleton className="h-28 w-full" />}
        {invitations.data?.length === 0 && (
          <EmptyState
            icon={MailPlusIcon}
            title="Приглашений пока нет"
            hint="Откройте подборку по потребности и отправьте приглашение с вилкой — контакты раскроются после принятия."
          />
        )}
        <div className="flex flex-col gap-3">
          {invitations.data?.map((invitation) => (
            <InvitationTrackerCard key={invitation.id} invitation={invitation} />
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="company-heading">
        <h2 id="company-heading" className="text-lg font-semibold text-heading">
          Компания
        </h2>
        {company.data ? (
          <CompanyCard company={company.data} />
        ) : (
          <Skeleton className="h-40 w-full" />
        )}
      </section>

      <VacanciesSection vacancies={vacancies.data ?? []} />
    </div>
  )
}

function NeedCard({ need }: { need: Need }) {
  return (
    <Link href={`/employer/needs/${need.id}`} className="block">
      <Card className="h-full p-4 transition-colors hover:border-primary">
        <p className="line-clamp-2 text-sm text-ink-2">{need.raw_text}</p>
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {need.spec_slug && (
            <Badge variant="accent">{SPEC_LABELS[need.spec_slug] ?? need.spec_slug}</Badge>
          )}
          {need.grade && <Badge variant="accent">{GRADE_LABELS[need.grade]}</Badge>}
          {need.stack_must.map((tech) => (
            <Badge key={tech}>{tech}</Badge>
          ))}
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {need.salary_from != null && need.salary_to != null
              ? formatSalary(need.salary_from, need.salary_to)
              : 'вилка не задана'}
          </span>
          <span>{formatDate(need.created_at)}</span>
        </div>
      </Card>
    </Link>
  )
}

function CompanyCard({ company }: { company: CompanySelf }) {
  const [current, setCurrent] = useState(company)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    name: company.name,
    description: company.description ?? '',
    industry: company.industry ?? '',
    site: company.site ?? '',
  })
  const [pending, setPending] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (pending) return
    setPending(true)
    try {
      const saved = await putCompany({
        name: form.name,
        description: form.description || null,
        industry: form.industry || null,
        site: form.site || null,
        contacts: current.contacts,
      })
      setCurrent(saved)
      setEditing(false)
      toast.success('Профиль компании сохранён')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось сохранить')
    } finally {
      setPending(false)
    }
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>{current.name}</CardTitle>
        <Button variant="outline" size="sm" onClick={() => setEditing((v) => !v)}>
          {editing ? 'Отмена' : 'Редактировать'}
        </Button>
      </CardHeader>
      <CardContent>
        {editing ? (
          <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-3">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              aria-label="Название компании"
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                value={form.industry}
                onChange={(e) => setForm({ ...form, industry: e.target.value })}
                placeholder="Направление"
                aria-label="Направление"
              />
              <Input
                value={form.site}
                onChange={(e) => setForm({ ...form, site: e.target.value })}
                placeholder="https://…"
                aria-label="Сайт"
              />
            </div>
            <Textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Описание компании"
              aria-label="Описание компании"
            />
            <Button type="submit" disabled={pending} className="self-start">
              {pending ? 'Сохраняем…' : 'Сохранить'}
            </Button>
          </form>
        ) : (
          <div className="flex flex-col gap-2 text-sm">
            <p className="text-muted-foreground">{current.industry ?? 'Направление не указано'}</p>
            {current.description && <p className="text-ink-2">{current.description}</p>}
            {current.site && (
              <a
                href={current.site}
                target="_blank"
                rel="noreferrer"
                className="text-primary hover:underline"
              >
                {current.site}
              </a>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
