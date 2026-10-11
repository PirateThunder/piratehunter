import { api } from '@/fsd/shared/api/http'
import type { VacancyFilters, VacancyPublic } from '@/fsd/shared/api/types'

/** Published vacancies for candidates (PRD §7.7; contract phase 3). */
export function fetchPublicVacancies(filters: VacancyFilters = {}) {
  const searchParams = Object.fromEntries(
    Object.entries(filters)
      .filter(([, v]) => v !== undefined && v !== '')
      .map(([k, v]) => [k, String(v)]),
  )
  return api.get('vacancies', { searchParams }).json<VacancyPublic[]>()
}

export interface ApplyOut {
  id: string
  status: 'sent'
  created_at: string
}

export function applyToVacancy(vacancyId: string, message: string) {
  return api.post(`vacancies/${vacancyId}/apply`, { json: { message } }).json<ApplyOut>()
}
