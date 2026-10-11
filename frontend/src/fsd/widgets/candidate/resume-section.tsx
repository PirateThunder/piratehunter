'use client'

import { FileUpIcon, LoaderCircleIcon } from 'lucide-react'
import { type DragEvent, useRef, useState } from 'react'
import { toast } from 'sonner'

import { uploadResume } from '@/fsd/entities/candidate/api/candidate-api'
import type { ResumeDraft } from '@/fsd/shared/api/types'
import { cn } from '@/fsd/shared/lib/utils'

const MAX_SIZE = 10 * 1024 * 1024 // 10 МБ

/**
 * Resume upload (PRD §7.10): modest drop-zone/button → PDF → LLM draft that
 * prefills the editable profile form. The backend never changes the profile
 * itself — the mandatory human review is enforced UI-side («Проверьте перед
 * сохранением» banner until the form is saved).
 */
export function ResumeSection({ onDraft }: { onDraft: (draft: ResumeDraft) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [pending, setPending] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [notes, setNotes] = useState<string | null>(null)

  function hasContent(draft: ResumeDraft): boolean {
    return Boolean(
      draft.spec ||
        draft.grade_claimed ||
        draft.stack.length ||
        draft.roles.length ||
        draft.experience_years != null ||
        draft.about,
    )
  }

  async function upload(file: File | undefined | null) {
    if (!file || pending) return
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Нужен PDF-файл')
      return
    }
    if (file.size > MAX_SIZE) {
      toast.error('Файл больше 10 МБ')
      return
    }
    setPending(true)
    setNotes(null)
    try {
      const { draft } = await uploadResume(file)
      if (hasContent(draft)) {
        onDraft(draft)
        setNotes(draft.notes)
        toast.success('Резюме разобрано — проверьте поля и сохраните')
      } else {
        setNotes(draft.notes ?? 'Разбор временно недоступен — заполните форму вручную.')
        toast.info(draft.notes ?? 'Разбор временно недоступен')
      }
    } catch (error) {
      // 422 (broken/not-a-PDF) arrives with a readable detail via http unwrap
      toast.error(error instanceof Error ? error.message : 'Не удалось разобрать резюме')
    } finally {
      setPending(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragOver(false)
    void upload(e.dataTransfer.files?.[0])
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-ink-2">Резюме</span>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        disabled={pending}
        className={cn(
          'flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-input bg-background px-4 py-5 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-foreground disabled:cursor-wait disabled:opacity-60',
          dragOver && 'border-primary bg-primary-soft text-foreground',
        )}
      >
        {pending ? (
          <LoaderCircleIcon className="size-4 animate-spin" aria-hidden />
        ) : (
          <FileUpIcon className="size-4" aria-hidden />
        )}
        {pending
          ? 'Разбираем резюме — до полуминуты…'
          : 'Загрузить PDF — система разберёт и предзаполнит форму'}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        aria-label="Файл резюме PDF"
        onChange={(e) => void upload(e.target.files?.[0])}
      />
      {notes && <p className="text-xs text-muted-foreground">{notes}</p>}
    </div>
  )
}
