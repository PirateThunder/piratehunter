'use client'

import { FileDownIcon, XIcon } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'

import { fetchProfilePdf, putCandidateProfile } from '@/fsd/entities/candidate/api/candidate-api'
import { fetchCatalog } from '@/fsd/entities/catalog/api/catalog-api'
import type { CandidateSelf, Grade, ProfileIn, ResumeDraft } from '@/fsd/shared/api/types'
import { downloadBlob } from '@/fsd/shared/lib/download'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { Badge } from '@/fsd/shared/ui/badge'
import { Button } from '@/fsd/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/fsd/shared/ui/card'
import { Field } from '@/fsd/shared/ui/field'
import { Input } from '@/fsd/shared/ui/input'
import { Select } from '@/fsd/shared/ui/select'
import { Skeleton } from '@/fsd/shared/ui/skeleton'
import { Textarea } from '@/fsd/shared/ui/textarea'
import { ResumeSection } from '@/fsd/widgets/candidate/resume-section'

/** Tag editor: Enter/comma adds, × removes (stack, roles, soft skills). */
function TagsInput({
  value,
  onChange,
  placeholder,
  label,
}: {
  value: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
  label: string
}) {
  const [draft, setDraft] = useState('')

  function add() {
    const tag = draft.trim()
    if (tag && !value.includes(tag)) onChange([...value, tag])
    setDraft('')
  }

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-ink-2">{label}</span>
      <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-input bg-background px-2 py-1.5">
        {value.map((tag) => (
          <Badge key={tag}>
            {tag}
            <button
              type="button"
              onClick={() => onChange(value.filter((t) => t !== tag))}
              aria-label={`Убрать ${tag}`}
              className="cursor-pointer text-muted-foreground hover:text-foreground"
            >
              <XIcon className="size-3" />
            </button>
          </Badge>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') {
              e.preventDefault()
              add()
            }
          }}
          onBlur={add}
          placeholder={placeholder}
          className="min-w-28 flex-1 bg-transparent text-sm outline-none placeholder:text-placeholder"
        />
      </div>
    </div>
  )
}

/** Editable candidate profile (PRD §7.2): full upsert via PUT /candidate/profile. */
export function ProfileSection({
  profile,
  onSaved,
}: {
  profile: CandidateSelf
  onSaved: (p: CandidateSelf) => void
}) {
  const catalog = useQuery(() => fetchCatalog())
  const [form, setForm] = useState<ProfileIn>({
    fio: profile.fio,
    phone: profile.phone ?? '',
    contacts: { ...profile.contacts },
    stack: [...profile.stack],
    spec_slug: profile.spec_slug,
    grade_claimed: profile.grade_claimed,
    experience_years: profile.experience_years,
    roles: [...profile.roles],
    soft_skills: [...profile.soft_skills],
    about: profile.about ?? '',
  })
  const [pending, setPending] = useState(false)
  const [pdfPending, setPdfPending] = useState(false)
  const [draftApplied, setDraftApplied] = useState(false)

  const contacts = (form.contacts ?? {}) as Record<string, string>

  /** LLM resume draft → editable form fields (only what the draft carries). */
  function applyDraft(draft: ResumeDraft) {
    setForm((f) => ({
      ...f,
      spec_slug: draft.spec ?? f.spec_slug,
      grade_claimed: draft.grade_claimed ?? f.grade_claimed,
      stack: draft.stack.length ? draft.stack : f.stack,
      roles: draft.roles.length ? draft.roles : f.roles,
      experience_years: draft.experience_years ?? f.experience_years,
      about: draft.about ?? f.about,
    }))
    setDraftApplied(true)
  }

  async function downloadPdf() {
    if (pdfPending) return
    setPdfPending(true)
    try {
      const blob = await fetchProfilePdf()
      downloadBlob(blob, 'piratehunter-profile.pdf')
      toast.success('PDF-профиль скачан')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'PDF-профиль пока недоступен')
    } finally {
      setPdfPending(false)
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (pending) return
    setPending(true)
    try {
      const saved = await putCandidateProfile({
        ...form,
        phone: form.phone || null,
        about: form.about || null,
        experience_years: form.experience_years ?? null,
      })
      onSaved(saved)
      setDraftApplied(false)
      toast.success('Профиль сохранён')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось сохранить профиль')
    } finally {
      setPending(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Профиль</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
          <ResumeSection onDraft={applyDraft} />
          {draftApplied && (
            <output className="block rounded-lg border border-primary/40 bg-primary-soft px-3 py-2 text-sm text-ink-2">
              Черновик из резюме подставлен в форму — <strong>проверьте перед сохранением</strong>.
            </output>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="ФИО">
              {(id) => (
                <Input
                  id={id}
                  value={form.fio}
                  onChange={(e) => setForm({ ...form, fio: e.target.value })}
                  required
                  maxLength={300}
                />
              )}
            </Field>
            <Field label="Специализация">
              {(id) =>
                catalog.data ? (
                  <Select
                    id={id}
                    value={form.spec_slug ?? ''}
                    onChange={(e) => setForm({ ...form, spec_slug: e.target.value || null })}
                  >
                    <option value="">— не выбрана —</option>
                    {catalog.data.specializations.map((s) => (
                      <option key={s.slug} value={s.slug}>
                        {s.title}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <Skeleton className="h-9" />
                )
              }
            </Field>
            <Field
              label="Заявляемый грейд"
              hint="Выбор самостоятельный; официально грейд присваивает только тест"
            >
              {(id) => (
                <Select
                  id={id}
                  value={form.grade_claimed ?? ''}
                  onChange={(e) =>
                    setForm({ ...form, grade_claimed: (e.target.value || null) as Grade | null })
                  }
                >
                  <option value="">— не выбран —</option>
                  {(catalog.data?.grades ?? []).map((g) => (
                    <option key={g.slug} value={g.slug}>
                      {g.title}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Стаж, лет">
              {(id) => (
                <Input
                  id={id}
                  type="number"
                  min={0}
                  max={60}
                  value={form.experience_years ?? ''}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      experience_years: e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              )}
            </Field>
          </div>

          <TagsInput
            label="Стек"
            value={form.stack ?? []}
            onChange={(stack) => setForm({ ...form, stack })}
            placeholder="Python, FastAPI…"
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Телефон">
              {(id) => (
                <Input
                  id={id}
                  type="tel"
                  value={form.phone ?? ''}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  placeholder="+7 …"
                />
              )}
            </Field>
            <Field label="Telegram">
              {(id) => (
                <Input
                  id={id}
                  value={contacts.telegram ?? ''}
                  onChange={(e) =>
                    setForm({ ...form, contacts: { ...contacts, telegram: e.target.value } })
                  }
                  placeholder="@username"
                />
              )}
            </Field>
          </div>
          <p className="text-xs text-muted-foreground">
            Контакты видны работодателю только после принятия приглашения (§7.6).
          </p>

          <Field label="О себе">
            {(id) => (
              <Textarea
                id={id}
                value={form.about ?? ''}
                onChange={(e) => setForm({ ...form, about: e.target.value })}
                maxLength={10000}
                placeholder="Опыт, проекты, что ищете"
              />
            )}
          </Field>

          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={pending}>
              {pending ? 'Сохраняем…' : 'Сохранить'}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => void downloadPdf()}
              disabled={pdfPending || !profile.fio}
              title={profile.fio ? undefined : 'Сначала заполните профиль'}
            >
              <FileDownIcon />
              {pdfPending ? 'Готовим PDF…' : 'Скачать PDF-профиль'}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

export function ProfileSectionSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-40" />
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-24 w-full" />
      </CardContent>
    </Card>
  )
}
