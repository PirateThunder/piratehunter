'use client'

import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { answerTest, startTestSession } from '@/fsd/entities/candidate/api/candidate-api'
import { fetchCatalog } from '@/fsd/entities/catalog/api/catalog-api'
import type { Catalog, Grade, TestMode, TestQuestion, TestResult } from '@/fsd/shared/api/types'
import { GRADE_STATUS_LABELS, gradeLabel, specLabel } from '@/fsd/shared/lib/format'
import { Badge } from '@/fsd/shared/ui/badge'
import { Button } from '@/fsd/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/fsd/shared/ui/card'
import { Skeleton } from '@/fsd/shared/ui/skeleton'
import { Textarea } from '@/fsd/shared/ui/textarea'

/** Expected question count per mode (PRD §7.4.2); the result carries the truth. */
const MODE_LENGTH: Record<TestMode, number> = { full: 10, express: 4 }

type Phase =
  | { name: 'setup' }
  | { name: 'question'; sessionId: string; question: TestQuestion; index: number; mode: TestMode }
  | { name: 'result'; result: TestResult }

/**
 * Adaptive test flow (money screen §7.11.2): grade target + mode → questions
 * with per-question countdown → result screen with θ, outcome and breakdown.
 */
export function TestFlow() {
  const [phase, setPhase] = useState<Phase>({ name: 'setup' })
  const [catalog, setCatalog] = useState<Catalog | null>(null)

  useEffect(() => {
    fetchCatalog()
      .then(setCatalog)
      .catch(() => toast.error('Не удалось загрузить каталог'))
  }, [])

  if (phase.name === 'setup') return <SetupPhase catalog={catalog} onStarted={setPhase} />
  if (phase.name === 'question') {
    return (
      <QuestionPhase
        key={`${phase.sessionId}:${phase.index}`}
        sessionId={phase.sessionId}
        question={phase.question}
        index={phase.index}
        mode={phase.mode}
        onPhase={setPhase}
      />
    )
  }
  return <ResultPhase result={phase.result} catalog={catalog} />
}

// ── Setup ────────────────────────────────────────────────────────────
function SetupPhase({
  catalog,
  onStarted,
}: {
  catalog: Catalog | null
  onStarted: (phase: Phase) => void
}) {
  const [grade, setGrade] = useState<Grade>('middle')
  const [mode, setMode] = useState<TestMode>('express')
  const [pending, setPending] = useState(false)

  async function start() {
    if (pending) return
    setPending(true)
    try {
      const data = await startTestSession(grade, mode)
      if (!data.question) throw new Error('Ядро не вернуло первый вопрос')
      onStarted({
        name: 'question',
        sessionId: data.session_id,
        question: data.question,
        index: 1,
        mode,
      })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Не удалось начать тест')
      setPending(false)
    }
  }

  return (
    <Card className="mx-auto max-w-xl">
      <CardHeader>
        <CardTitle>Адаптивный тест на грейд</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <p className="text-sm text-muted-foreground">
          Вопросы подбираются под ваши ответы (CAT-lite): каждый экземпляр задания уникален, на
          вопрос — таймер. По итогам присваивается категория «специализация × грейд».
        </p>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium text-ink-2">Заявляемый грейд</legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(catalog?.grades ?? []).map((g) => (
              <button
                key={g.slug}
                type="button"
                onClick={() => setGrade(g.slug)}
                aria-pressed={grade === g.slug}
                className={`cursor-pointer rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  grade === g.slug
                    ? 'border-primary bg-primary-soft text-primary'
                    : 'border-border bg-card text-foreground hover:border-primary/50'
                }`}
              >
                {g.title}
              </button>
            ))}
            {!catalog && (
              <>
                <Skeleton className="h-9" />
                <Skeleton className="h-9" />
                <Skeleton className="h-9" />
                <Skeleton className="h-9" />
              </>
            )}
          </div>
          {catalog && (
            <p className="text-xs text-muted-foreground">
              {catalog.grades.find((g) => g.slug === grade)?.description}
            </p>
          )}
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium text-ink-2">Режим</legend>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setMode('express')}
              aria-pressed={mode === 'express'}
              className={`cursor-pointer rounded-lg border p-3 text-left transition-colors ${
                mode === 'express'
                  ? 'border-primary bg-primary-soft'
                  : 'border-border bg-card hover:border-primary/50'
              }`}
            >
              <span className="block text-sm font-medium text-foreground">
                Экспресс · 4 вопроса
              </span>
              <span className="block text-xs text-muted-foreground">3–5 минут, точность ниже</span>
            </button>
            <button
              type="button"
              onClick={() => setMode('full')}
              aria-pressed={mode === 'full'}
              className={`cursor-pointer rounded-lg border p-3 text-left transition-colors ${
                mode === 'full'
                  ? 'border-primary bg-primary-soft'
                  : 'border-border bg-card hover:border-primary/50'
              }`}
            >
              <span className="block text-sm font-medium text-foreground">
                Полный · 10 вопросов
              </span>
              <span className="block text-xs text-muted-foreground">точная калибровка θ</span>
            </button>
          </div>
        </fieldset>

        <Button size="lg" onClick={() => void start()} disabled={pending || !catalog}>
          {pending ? 'Готовим вопросы…' : 'Начать тест'}
        </Button>
      </CardContent>
    </Card>
  )
}

// ── Question ─────────────────────────────────────────────────────────
function QuestionPhase({
  sessionId,
  question,
  index,
  mode,
  onPhase,
}: {
  sessionId: string
  question: TestQuestion
  index: number
  mode: TestMode
  onPhase: (phase: Phase) => void
}) {
  const total = MODE_LENGTH[mode]
  const [selected, setSelected] = useState<number | null>(null)
  const [sql, setSql] = useState('')
  const [left, setLeft] = useState(question.time_limit)
  const [pending, setPending] = useState(false)
  const submittedRef = useRef(false)

  const submit = useCallback(
    async (answer: string | number | null) => {
      if (submittedRef.current) return
      submittedRef.current = true
      setPending(true)
      try {
        const data = await answerTest(sessionId, answer)
        if (data.result) onPhase({ name: 'result', result: data.result })
        else if (data.next_question)
          onPhase({
            name: 'question',
            sessionId,
            question: data.next_question,
            index: index + 1,
            mode,
          })
        else throw new Error('Пустой ответ ядра')
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Не удалось отправить ответ')
        submittedRef.current = false
        setPending(false)
      }
    },
    [sessionId, index, mode, onPhase],
  )

  // Per-question countdown (PRD §7.4.2); timeout auto-submits the current answer.
  useEffect(() => {
    const timer = setInterval(() => setLeft((v) => Math.max(0, v - 1)), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (left === 0) void submit(question.type === 'mcq' ? selected : sql.trim() || null)
  }, [left, question.type, selected, sql, submit])

  const text = question.instance.question_text.split('```')[0].trim()
  const code = question.instance.payload.code
  const options = question.instance.payload.options
  const canSubmit = question.type === 'mcq' ? selected !== null : sql.trim().length > 0
  const overtime = left <= 10

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Вопрос <span className="font-mono font-semibold text-ink">{index}</span>
          {index <= total && (
            <>
              {' '}
              из <span className="font-mono tabular-nums">{total}</span>
            </>
          )}
        </p>
        <Badge variant={overtime ? 'danger' : 'default'} aria-live="polite">
          <span className="font-mono tabular-nums">
            {Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}
          </span>
        </Badge>
      </div>
      <div className="h-1.5 overflow-hidden rounded-pill bg-muted" role="presentation">
        <div
          className="h-full rounded-pill bg-primary transition-all"
          style={{ width: `${Math.min(100, ((index - 1) / total) * 100)}%` }}
        />
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4 pt-4">
          <p className="text-pretty text-ink-2">{text}</p>
          {code && (
            <pre className="overflow-x-auto rounded-lg bg-ink p-4 font-mono text-sm text-background">
              <code>{code}</code>
            </pre>
          )}

          {question.type === 'mcq' && options && (
            <div className="flex flex-col gap-2">
              {options.map((option, i) => (
                <button
                  key={`${i}-${option}`}
                  type="button"
                  aria-pressed={selected === i}
                  onClick={() => setSelected(i)}
                  className={`cursor-pointer rounded-lg border px-4 py-3 text-left font-mono text-sm transition-colors ${
                    selected === i
                      ? 'border-primary bg-primary-soft text-ink'
                      : 'border-border bg-card hover:border-primary/50'
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
          )}

          {question.type === 'sql' && (
            <div className="flex flex-col gap-2">
              {question.instance.payload.schema && (
                <pre className="overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs text-ink-2">
                  {question.instance.payload.schema}
                </pre>
              )}
              <Textarea
                value={sql}
                onChange={(e) => setSql(e.target.value)}
                placeholder="SELECT ..."
                aria-label="SQL-запрос"
                className="min-h-32 font-mono text-sm"
              />
              {question.instance.payload.columns && (
                <p className="text-xs text-muted-foreground">
                  Колонки результата: {question.instance.payload.columns.join(', ')}
                </p>
              )}
            </div>
          )}

          <Button
            onClick={() => void submit(question.type === 'mcq' ? selected : sql.trim())}
            disabled={!canSubmit || pending}
          >
            {pending ? 'Проверяем…' : 'Ответить'}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

// ── Result ───────────────────────────────────────────────────────────
function ResultPhase({ result, catalog }: { result: TestResult; catalog: Catalog | null }) {
  const router = useRouter()
  const correct = result.asked.filter((a) => a.correct).length

  return (
    <Card className="mx-auto max-w-xl">
      <CardHeader>
        <CardTitle>Результат теста</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={result.outcome === 'confirmed' ? 'success' : 'accent'}>
            {GRADE_STATUS_LABELS[result.outcome]}
          </Badge>
          {result.mode === 'express' && (
            <Badge variant="outline">экспресс-режим — точность понижена</Badge>
          )}
        </div>

        <p className="text-lg text-ink-2">
          Категория:{' '}
          <span className="font-semibold text-heading">{specLabel(catalog, result.spec)}</span>
          {' × '}
          <span className="font-semibold text-heading">
            {gradeLabel(catalog, result.grade_assigned)}
          </span>
          {result.grade_verified && <span className="text-success"> — подтверждено тестом</span>}
        </p>

        <div className="grid grid-cols-3 gap-3 rounded-xl bg-muted p-4 text-center">
          <div>
            <p className="font-mono text-2xl font-semibold text-ink tabular-nums">
              θ={result.theta.toFixed(2)}
            </p>
            <p className="text-xs text-muted-foreground">оценка способности</p>
          </div>
          <div>
            <p className="font-mono text-2xl font-semibold text-ink tabular-nums">
              {correct}/{result.asked.length}
            </p>
            <p className="text-xs text-muted-foreground">верных ответов</p>
          </div>
          <div>
            <p className="font-mono text-2xl font-semibold text-ink tabular-nums">
              {result.se.toFixed(2)}
            </p>
            <p className="text-xs text-muted-foreground">погрешность SE</p>
          </div>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-ink-2">По темам</p>
          <ul className="flex flex-col gap-1.5">
            {Object.entries(result.breakdown).map(([topic, stat]) => (
              <li
                key={topic}
                className="flex items-center justify-between rounded-lg bg-muted px-3 py-1.5 text-sm"
              >
                <span className="text-ink-2">{topic}</span>
                <span className="font-mono tabular-nums">
                  {stat.correct}/{stat.asked}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-muted-foreground">
          {result.outcome === 'upgrade_offer' &&
            'Отличный результат — доступен тест на грейд выше в кабинете.'}
          {result.outcome === 'downgrade_offer' &&
            'Грейд не понижается принудительно: в кабинете доступен тест на уровень ниже, попытка не сгорает.'}
          {result.outcome === 'confirmed' && 'Категория присвоена — вы видны работодателям в ней.'}
        </p>

        <Button onClick={() => router.push('/candidate')}>В кабинет</Button>
      </CardContent>
    </Card>
  )
}
