/*
 * Contract types of the backend `/api/v1` (PRD §8.1), verified against the
 * live OpenAPI (localhost:64844/openapi.json) on 2026-10-08. Where the live
 * backend disagrees with the PRD table, the live shape wins (see AGENTS.md).
 */

// ── Catalogs (PRD §6, live GET /catalog) ─────────────────────────────
export type Role = 'candidate' | 'employer'

/** Spec slugs come from the live catalog — keep it a string, not a union. */
export type SpecSlug = string

/** Grade = skill level verified by the test, not years of experience */
export type Grade = 'intern' | 'junior' | 'middle' | 'senior'

export type GradeStatus = 'unverified' | 'confirmed' | 'upgrade_offer' | 'downgrade_offer'

export type SalaryType = 'gross' | 'net'

export type InvitationStatus = 'sent' | 'viewed' | 'accepted' | 'declined'

export interface CatalogTopic {
  slug: string
  title: string
}

export interface CatalogSpec {
  slug: SpecSlug
  title: string
  topics: CatalogTopic[]
}

export interface CatalogGrade {
  slug: Grade
  title: string
  lo: number
  hi: number
  description: string
}

export interface Catalog {
  specializations: CatalogSpec[]
  grades: CatalogGrade[]
  theta_scale?: Record<string, unknown>
}

// ── Candidate (PRD §7.2) ─────────────────────────────────────────────
export interface Privacy {
  anonymous: boolean
  show_fsp: boolean
  show_stack: boolean
}

/** ФСП block in a profile card: score + raw registry document (§7.9) */
export interface FspBlock {
  score: number
  achievements: Record<string, unknown>
}

/** Public part of a candidate — what the employer sees (contacts excluded) */
export interface CandidatePublic {
  candidate_id: string
  fio: string
  spec_slug: SpecSlug | null
  grade_claimed: Grade | null
  grade_verified: Grade | null
  grade_status: GradeStatus
  experience_years: number | null
  stack: string[]
  roles: string[]
  soft_skills: string[]
  about: string | null
  has_fsp: boolean
  fsp: FspBlock | null
  updated_at: string
}

export interface CandidateContacts {
  email: string | null
  phone: string | null
  contacts: Record<string, unknown>
}

/** Candidate as seen by the employer: public profile + contacts after accept */
export interface CandidateEmployer {
  profile: CandidatePublic
  contacts: CandidateContacts | null
}

/** Own profile (GET /candidate/profile): public part + contacts + privacy */
export interface CandidateSelf extends CandidatePublic {
  email: string | null
  phone: string | null
  contacts: Record<string, unknown>
  privacy: Privacy
  fsp_id: string | null
}

/** PUT /candidate/profile — full replacement (upsert) */
export interface ProfileIn {
  fio: string
  phone?: string | null
  contacts?: Record<string, unknown>
  stack?: string[]
  spec_slug?: SpecSlug | null
  grade_claimed?: Grade | null
  experience_years?: number | null
  roles?: string[]
  soft_skills?: string[]
  about?: string | null
  privacy?: Partial<Privacy>
}

// ── Resume parsing (PRD §7.10, phase 3; not yet deployed 2026-10-08) ──
/**
 * POST /candidate/profile/resume (multipart PDF) → draft for form prefill
 * ONLY (the profile itself is untouched; human review is mandatory).
 * A 200 with an empty draft + notes means parsing is temporarily unavailable;
 * 422 = broken/not-a-PDF with a readable detail.
 */
export interface ResumeDraft {
  spec: SpecSlug | null
  grade_claimed: Grade | null
  stack: string[]
  roles: string[]
  experience_years: number | null
  about: string | null
  confidence: number | null
  notes: string | null
}

export interface ResumeParseOut {
  draft: ResumeDraft
}

/** GET /candidate/grade: status, cooldowns, position in the category */
export interface GradeInfo {
  spec_slug: SpecSlug | null
  grade_claimed: Grade | null
  grade_verified: Grade | null
  status: GradeStatus
  theta: number | null
  last_test_at: string | null
  grade_changed_at: string | null
  retest_available_at: string | null
  change_available_at: string | null
  category_rank: number | null
  category_size: number | null
}

// ── Tests (PRD §7.4, proxied from core) ──────────────────────────────
export type TestMode = 'full' | 'express'

export interface McqPayload {
  code?: string
  options: string[]
}

export interface SqlPayload {
  setup_sql?: string
  schema?: string
  columns?: string[]
}

export interface TestQuestion {
  template_id: string
  topic: string
  type: 'mcq' | 'sql'
  /** Seconds per question (mcq 90, sql 240) */
  time_limit: number
  instance: {
    question_text: string
    payload: McqPayload & SqlPayload
    beta: number
  }
}

export interface TestSessionStarted {
  session_id: string
  question: TestQuestion | null
}

export interface AskedItem {
  template_id: string
  topic: string
  kind: string
  beta: number
  correct: boolean
  theta_after: number
}

export interface TestResult {
  theta: number
  se: number
  outcome: GradeStatus
  grade_verified: Grade | null
  grade_assigned: Grade
  grade_claimed: Grade
  spec: SpecSlug
  mode: TestMode
  p_upgrade: number
  p_downgrade: number
  asked: AskedItem[]
  /** topic → {asked, correct} */
  breakdown: Record<string, { asked: number; correct: number }>
}

/** Answer response: exactly one of next_question / result is set */
export interface TestAnswerOut {
  next_question: TestQuestion | null
  result: TestResult | null
}

// ── Employer (PRD §7.3) ──────────────────────────────────────────────
export interface CompanyPublic {
  company_id: string
  name: string
  description: string | null
  industry: string | null
  site: string | null
}

export interface CompanyContacts {
  contacts: Record<string, unknown>
}

export interface CompanyCandidate {
  company: CompanyPublic
  contacts: CompanyContacts | null
}

export interface CompanySelf {
  company_id: string
  name: string
  description: string | null
  industry: string | null
  contacts: Record<string, unknown>
  site: string | null
}

export interface CompanyIn {
  name: string
  description?: string | null
  industry?: string | null
  contacts?: Record<string, unknown>
  site?: string | null
}

export interface Need {
  id: string
  company_id: string
  raw_text: string
  parsed: Record<string, unknown> | null
  stack_must: string[]
  stack_nice: string[]
  spec_slug: SpecSlug | null
  grade: Grade | null
  salary_from: number | null
  salary_to: number | null
  created_at: string
}

export interface NeedIn {
  raw_text: string
  stack_must?: string[]
  stack_nice?: string[]
  spec_slug?: SpecSlug | null
  grade?: Grade | null
  salary_from?: number | null
  salary_to?: number | null
}

/** POST /employer/needs/parse (new in phase 2; not yet deployed 2026-10-08) */
export interface NeedParseOut {
  spec: SpecSlug | null
  grade: Grade | null
  stack_must: string[]
  stack_nice: string[]
  confidence: number | null
  notes: string | null
}

// ── Matching (PRD §7.5) ──────────────────────────────────────────────
/** Explainability factor (§7.5.3): human_text + weighted contribution bars */
export interface ExplanationFactor {
  factor: string
  weight: number
  value: number
  contribution: number
  human_text: string
}

export interface ShortlistItem {
  candidate: CandidateEmployer
  score: number
  explanation: ExplanationFactor[]
  /** false → блок «рядом с запросом» (вне категории); absent in early deploys */
  in_category?: boolean
}

export interface Shortlist {
  need_id: string
  results: ShortlistItem[]
}

/** GET /employer/market/salary (new in phase 2; null fields on empty sample) */
export interface SalaryMarket {
  spec: SpecSlug
  grade: Grade
  category_size: number
  sample_needs: number
  sample_invitations: number
  from_p25: number | null
  from_p50: number | null
  from_p75: number | null
  to_p25: number | null
  to_p50: number | null
  to_p75: number | null
}

// ── Invitations (PRD §7.6) ───────────────────────────────────────────
interface InvitationBase {
  id: string
  text: string
  salary_from: number
  salary_to: number
  salary_type: SalaryType
  contact_method: string
  status: InvitationStatus
  created_at: string
  status_at: string
}

/** Incoming at the candidate: company (contacts — after accept) */
export interface InvitationCandidate extends InvitationBase {
  company: CompanyCandidate
}

/** Outgoing at the employer: candidate (contacts — after accept) */
export interface InvitationEmployer extends InvitationBase {
  candidate: CandidateEmployer
}

export interface InvitationCreateIn {
  candidate_id: string
  text: string
  salary_from: number
  salary_to: number
  salary_type: SalaryType
  contact_method: string
}

/** Accept response: contacts of BOTH sides revealed (§7.2) */
export interface InvitationAcceptOut {
  invitation: InvitationCandidate
}
