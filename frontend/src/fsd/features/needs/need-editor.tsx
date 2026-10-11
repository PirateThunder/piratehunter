'use client'

import { SparklesIcon } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'

import { fetchCatalog } from '@/fsd/entities/catalog/api/catalog-api'
import { createNeed, parseNeed, updateNeed } from '@/fsd/entities/employer/api/employer-api'
import type { Grade, Need, NeedIn } from '@/fsd/shared/api/types'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { Badge } from '@/fsd/shared/ui/badge'
import { Button } from '@/fsd/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/fsd/shared/ui/card'
import { Field } from '@/fsd/shared/ui/field'
import { Input } from '@/fsd/shared/ui/input'
import { Select } from '@/fsd/shared/ui/select'
import { Skeleton } from '@/fsd/shared/ui/skeleton'
import { Textarea } from '@/fsd/shared/ui/textarea'
import { SalaryMarketWidget } from '@/fsd/widgets/employer/salary-market-widget'

interface Draft {
  raw_text: string
  spec_slug: string
  grade: string
  stack_must: string[]
  stack_nice: string[]
  salary_from: string
  salary_to: string
}

function toDraft(need?: Need | null): Draft {
  return {
    raw_text: need?.raw_text ?? '',
    spec_slug: need?.spec_slug ?? '',
    grade: need?.grade ?? '',
    stack_must: need?.stack_must ?? [],
    stack_nice: need?.stack_nice ?? [],
    salary_from: need?.salary_from != null ? String(need.salary_from) : '',
    salary_to: need?.salary_to != null ? String(need.salary_to) : '',
  }
}

/** Compact tag editor for must/nice stacks. */
function TagEditor({
  label,
  tags,
  onChange,
}: {
  label: string
  tags: string[]
  onChange: (tags: string[]) => void
}) {
  const [draft, setDraft] = useState('')
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-ink-2">{label}</span>
      <div className="flex flex-wrap items-center gap-1.5">
        {tags.map((tag) => (
          <Badge key={tag}>
            {tag}
            <button
              type="button"
              aria-label={`Убрать ${tag}`}
              onClick={() => onChange(tags.filter((t) => t !== tag))}
              className="cursor-pointer text-muted-foreground hover:text-foreground"
            >
              ×
            </button>
          </Badge>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ',') && draft.trim()) {
              e.preventDefault()
              if (!tags.includes(draft.trim())) onChange([...tags, draft.trim()])
              setDraft('')
            }
          }}
          placeholder="добавить…"
          className="h-7 min-w-24 flex-1 rounded-md border border-input bg-background px-2 text-sm outline-none placeholder:text-placeholder focus-visible:border-ring"
        />
      </div>
    </div>
  )
}

/*
 * Need editor (PRD §7.3): free text → «Разобрать» (LLM parse, §7.5.1) →
 * editable structured panel «мы поняли так» → save. The salary-range vs
 * market widget (§7.5.5) sits next to the salary inputs.
 */
export function NeedEditor({
  need,
  onSaved,
}: {
  need?: Need | null
  onSaved: (need: Need) => void
}) {
  const catalog = useQuery(() => fetchCatalog())
  const [form, setForm] = useState<Draft>(() => toDraft(need))
  const [parsing, setParsing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [parsedNotes, setParsedNotes] = useState<string | null>(null)

  async function parse() {
    if (parsing || !form.raw_text.trim()) return
    setParsing(true)
    try {
      const parsed = await parseNeed(form.raw_text.trim())
      setForm((f) => ({
        ...f,
        spec_slug: parsed.spec ?? f.spec_slug,
        grade: parsed.grade ?? f.grade,
        stack_must: parsed.stack_must.length ? parsed.stack_must : f.stack_must,
        stack_nice: parsed.stack_nice.length ? parsed.stack_nice : f.stack_nice,
      }))
      setParsedNotes(parsed.notes)
      toast.success('Разобрали потребность — проверьте и поправьте')
    } catch (error) {
      // parse endpoint lands in phase 2 backend; degrade to manual editing
      toast.error(
        error instanceof Error ? error.message : 'Разбор недоступен — заполните структуру вручную',
      )
    } finally {
      setParsing(false)
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (saving) return
    const from = form.salary_from ? Number(form.salary_from) : null
    const to = form.salary_to ? Number(form.salary_to) : null
    if (from != null && to != null && from > to) {
      toast.error('Вилка: «от» больше «до»')
      return
    }
    setSaving(true)
    const body: NeedIn = {
      raw_text: form.raw_text.trim(),
      spec_slug: form.spec_slug || null,
      grade: (form.grade || null) as Grade | null,
      stack_must: form.stack_must,
      stack_nice: form.stack_nice,
      salary_from: from,
      salary_to: to,
    }
    try {
      const saved = need ? await updateNeed(need.id, body) : await createNeed(body)
      onSaved(saved)
      toast.success('Потребность сохранена')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось сохранить потребность')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>{need ? 'Редактировать потребность' : 'Новая потребность'}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field label="Свободный текст">
            {(id) => (
              <Textarea
                id={id}
                value={form.raw_text}
                onChange={(e) => setForm({ ...form, raw_text: e.target.value })}
                placeholder="Нужен бэкенд-разработчик на Python уровня middle…"
                required
                maxLength={20000}
                className="min-h-28"
              />
            )}
          </Field>
          <Button
            type="button"
            variant="secondary"
            onClick={() => void parse()}
            disabled={parsing || !form.raw_text.trim()}
            className="self-start"
          >
            <SparklesIcon />
            {parsing ? 'Разбираем…' : 'Разобрать'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Мы поняли так — проверьте и поправьте</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Специализация">
              {(id) =>
                catalog.data ? (
                  <Select
                    id={id}
                    value={form.spec_slug}
                    onChange={(e) => setForm({ ...form, spec_slug: e.target.value })}
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
            <Field label="Грейд">
              {(id) => (
                <Select
                  id={id}
                  value={form.grade}
                  onChange={(e) => setForm({ ...form, grade: e.target.value })}
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
          </div>

          <TagEditor
            label="Стек — обязательный (must)"
            tags={form.stack_must}
            onChange={(stack_must) => setForm({ ...form, stack_must })}
          />
          <TagEditor
            label="Стек — будет плюсом (nice)"
            tags={form.stack_nice}
            onChange={(stack_nice) => setForm({ ...form, stack_nice })}
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Вилка от, ₽">
              {(id) => (
                <Input
                  id={id}
                  type="number"
                  min={0}
                  step={5000}
                  value={form.salary_from}
                  onChange={(e) => setForm({ ...form, salary_from: e.target.value })}
                  placeholder="200 000"
                />
              )}
            </Field>
            <Field label="Вилка до, ₽">
              {(id) => (
                <Input
                  id={id}
                  type="number"
                  min={0}
                  step={5000}
                  value={form.salary_to}
                  onChange={(e) => setForm({ ...form, salary_to: e.target.value })}
                  placeholder="280 000"
                />
              )}
            </Field>
          </div>

          <SalaryMarketWidget
            spec={form.spec_slug || null}
            grade={(form.grade || null) as Grade | null}
            from={form.salary_from ? Number(form.salary_from) : null}
            to={form.salary_to ? Number(form.salary_to) : null}
          />

          {parsedNotes && (
            <p className="rounded-lg bg-primary-soft p-3 text-xs text-ink-2">{parsedNotes}</p>
          )}

          <Button type="submit" disabled={saving} className="self-start">
            {saving ? 'Сохраняем…' : need ? 'Сохранить изменения' : 'Создать потребность'}
          </Button>
        </CardContent>
      </Card>
    </form>
  )
}
