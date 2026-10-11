import { api } from '@/fsd/shared/api/http'
import type {
  ApplicationEmployer,
  CandidateEmployer,
  CompanyIn,
  CompanySelf,
  Grade,
  InvitationCreateIn,
  InvitationEmployer,
  Need,
  NeedIn,
  NeedParseOut,
  SalaryMarket,
  Shortlist,
  SpecSlug,
  Vacancy,
  VacancyIn,
} from '@/fsd/shared/api/types'

/** Live backend calls of the employer cabinet (contract PRD §8.1). */
export function fetchCompany() {
  return api.get('employer/company').json<CompanySelf>()
}

export function putCompany(body: CompanyIn) {
  return api.put('employer/company', { json: body }).json<CompanySelf>()
}

// ── Needs ────────────────────────────────────────────────────────────
export function fetchNeeds() {
  return api.get('employer/needs').json<Need[]>()
}

export function fetchNeed(id: string) {
  return api.get(`employer/needs/${id}`).json<Need>()
}

export function createNeed(body: NeedIn) {
  return api.post('employer/needs', { json: body }).json<Need>()
}

export function updateNeed(id: string, body: NeedIn) {
  return api.put(`employer/needs/${id}`, { json: body }).json<Need>()
}

export function deleteNeed(id: string) {
  return api.delete(`employer/needs/${id}`).json()
}

/** «Разобрать» свободный текст потребности в структуру (LLM, fallback keyword) */
export function parseNeed(rawText: string) {
  return api.post('employer/needs/parse', { json: { raw_text: rawText } }).json<NeedParseOut>()
}

export function fetchShortlist(needId: string) {
  return api.get(`employer/needs/${needId}/shortlist`).json<Shortlist>()
}

// ── Candidate bank ───────────────────────────────────────────────────
export interface CandidateFilters {
  spec?: SpecSlug
  grade?: Grade
  stack?: string
  fsp?: boolean
  category?: string
  limit?: number
  offset?: number
}

export function fetchCandidates(filters: CandidateFilters = {}) {
  const searchParams = Object.fromEntries(
    Object.entries(filters)
      .filter(([, v]) => v !== undefined && v !== '')
      .map(([k, v]) => [k, String(v)]),
  )
  return api.get('employer/candidates', { searchParams }).json<CandidateEmployer[]>()
}

// ── Invitations ──────────────────────────────────────────────────────
export function fetchEmployerInvitations() {
  return api.get('employer/invitations').json<InvitationEmployer[]>()
}

export function createInvitation(body: InvitationCreateIn) {
  return api.post('employer/invitations', { json: body }).json<InvitationEmployer>()
}

// ── Salary market widget (PRD §7.5.5) ────────────────────────────────
export function fetchSalaryMarket(spec: SpecSlug, grade: Grade) {
  return api.get('employer/market/salary', { searchParams: { spec, grade } }).json<SalaryMarket>()
}

// ── Vacancies (PRD §7.7; contract phase 3) ───────────────────────────
export function fetchVacancies() {
  return api.get('employer/vacancies').json<Vacancy[]>()
}

export function fetchVacancy(id: string) {
  return api.get(`employer/vacancies/${id}`).json<Vacancy>()
}

export function createVacancy(body: VacancyIn) {
  // 201 on create; 200 on idempotent upsert by external_id
  return api.post('employer/vacancies', { json: body }).json<Vacancy>()
}

export function updateVacancy(id: string, body: VacancyIn) {
  return api.put(`employer/vacancies/${id}`, { json: body }).json<Vacancy>()
}

export function deleteVacancy(id: string) {
  return api.delete(`employer/vacancies/${id}`)
}

export function publishVacancy(id: string) {
  return api.post(`employer/vacancies/${id}/publish`).json<Vacancy>()
}

export function closeVacancy(id: string) {
  return api.post(`employer/vacancies/${id}/close`).json<Vacancy>()
}

export function fetchVacancyApplications(vacancyId: string) {
  return api.get(`employer/vacancies/${vacancyId}/applications`).json<ApplicationEmployer[]>()
}

export function patchApplicationStatus(id: string, status: 'viewed' | 'invited' | 'rejected') {
  return api.patch(`employer/applications/${id}`, { json: { status } }).json<ApplicationEmployer>()
}
