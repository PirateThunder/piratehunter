const CANDIDATE_STEPS = [
  'Регистрация по email-коду или через FSP ID',
  'Профиль: форма или PDF-резюме, стек и роли',
  'Опрос по специализации и выбор заявляемого грейда',
  'Адаптивный тест → категория «специализация × грейд»',
  'Приглашения с вилкой ЗП — контакты раскрываются после принятия',
] as const

const EMPLOYER_STEPS = [
  'Регистрация и профиль компании',
  'Потребность свободным текстом — система разбирает в структуру',
  'Подборка: категории и кандидаты с объяснением «почему»',
  'Приглашение конкретному человеку с обязательной вилкой ЗП',
] as const

function StepList({ steps }: { steps: readonly string[] }) {
  return (
    <ol className="flex flex-col gap-3">
      {steps.map((step, i) => (
        <li key={step} className="flex items-start gap-3">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary-soft font-mono text-sm font-semibold text-primary">
            {i + 1}
          </span>
          <span className="pt-0.5 text-ink-2">{step}</span>
        </li>
      ))}
    </ol>
  )
}

/** «Как это работает» — the two mirrored journeys of the reversed mechanic. */
export function HowItWorksSection() {
  return (
    <section id="how-it-works" className="bg-secondary/60 px-4 py-16">
      <div className="mx-auto flex max-w-6xl flex-col gap-10">
        <h2 className="text-3xl font-bold text-heading">Как это работает</h2>
        <div className="grid gap-6 md:grid-cols-2">
          <div
            id="candidate"
            className="flex scroll-mt-20 flex-col gap-5 rounded-xl border border-border bg-card p-6"
          >
            <h3 className="text-xl font-semibold text-heading">Для кандидата</h3>
            <StepList steps={CANDIDATE_STEPS} />
          </div>
          <div
            id="employer"
            className="flex scroll-mt-20 flex-col gap-5 rounded-xl border border-border bg-card p-6"
          >
            <h3 className="text-xl font-semibold text-heading">Для работодателя</h3>
            <StepList steps={EMPLOYER_STEPS} />
          </div>
        </div>
      </div>
    </section>
  )
}
