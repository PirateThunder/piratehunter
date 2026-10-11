import type { Catalog, Grade, GradeStatus, SalaryType, SpecSlug } from '@/fsd/shared/api/types'

/** Fallback labels; the live catalog (GET /catalog) is the source of truth. */
export const SPEC_LABELS: Record<string, string> = {
  backend: 'Бэкенд',
  frontend: 'Фронтенд',
  fullstack: 'Фулстек',
  mobile: 'Мобильная разработка',
  qa: 'QA',
  devops: 'DevOps',
  'data-ml': 'Data / ML',
}

export function specLabel(catalog: Catalog | null, slug: SpecSlug | null): string {
  if (!slug) return '—'
  return catalog?.specializations.find((s) => s.slug === slug)?.title ?? SPEC_LABELS[slug] ?? slug
}

export const GRADE_LABELS: Record<Grade, string> = {
  intern: 'Стажёр',
  junior: 'Джуниор',
  middle: 'Мидл',
  senior: 'Сеньор',
}

export function gradeLabel(catalog: Catalog | null, slug: Grade | null): string {
  if (!slug) return '—'
  return catalog?.grades.find((g) => g.slug === slug)?.title ?? GRADE_LABELS[slug] ?? slug
}

export const GRADE_STATUS_LABELS: Record<GradeStatus, string> = {
  unverified: 'не подтверждён',
  confirmed: 'подтверждён тестом',
  upgrade_offer: 'предложено повышение',
  downgrade_offer: 'предложен грейд ниже',
}

const rub = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

export function formatRub(value: number): string {
  return `${rub.format(value)} ₽`
}

/** «220 000 – 280 000 ₽»; the salary type is labeled separately (ТЗ: явно) */
export function formatSalary(from: number, to: number): string {
  return `${rub.format(from)} – ${rub.format(to)} ₽`
}

export function salaryTypeLabel(type: SalaryType): string {
  return type === 'gross' ? 'до вычета налогов' : 'на руки'
}

const dateFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })

export function formatDate(iso: string): string {
  return dateFmt.format(new Date(iso))
}

const dateTimeFmt = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatDateTime(iso: string): string {
  return dateTimeFmt.format(new Date(iso))
}
