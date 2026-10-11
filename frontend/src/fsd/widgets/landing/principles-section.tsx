import { BanknoteIcon, EyeOffIcon, ListChecksIcon, ScanSearchIcon } from 'lucide-react'

const PRINCIPLES = [
  {
    icon: BanknoteIcon,
    title: 'Вилка ЗП всегда видна',
    text: 'Зарплатная вилка обязательна в каждом приглашении и вакансии — кандидат отвечает, уже зная условия.',
  },
  {
    icon: EyeOffIcon,
    title: 'Контакты скрыты до принятия',
    text: 'Работодатель видит профиль и достижения, но не контакты. Они раскрываются обеим сторонам только после accept.',
  },
  {
    icon: ListChecksIcon,
    title: 'Грейд подтверждает тест',
    text: 'Категория — не самоописание: опрос, выбор грейда и адаптивный тест с уникальными экземплярами заданий.',
  },
  {
    icon: ScanSearchIcon,
    title: 'Объяснимая подборка',
    text: 'Каждый результат сопровождается разложением скора по факторам: тест, стек, достижения ФСП, свежесть.',
  },
] as const

/** Product principles — the four differentiators in one strip. */
export function PrinciplesSection() {
  return (
    <section id="principles" className="px-4 py-16">
      <div className="mx-auto flex max-w-6xl flex-col gap-10">
        <h2 className="text-3xl font-bold text-heading">Принципы платформы</h2>
        <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {PRINCIPLES.map(({ icon: Icon, title, text }) => (
            <li
              key={title}
              className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5"
            >
              <Icon className="size-6 text-primary" aria-hidden />
              <p className="font-semibold text-heading">{title}</p>
              <p className="text-sm text-muted-foreground">{text}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
