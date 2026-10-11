import { api } from '@/fsd/shared/api/http'
import type {
  CandidateSelf,
  Grade,
  GradeInfo,
  InvitationAcceptOut,
  InvitationCandidate,
  InvitationStatus,
  ProfileIn,
  ResumeParseOut,
  TestAnswerOut,
  TestMode,
  TestSessionStarted,
} from '@/fsd/shared/api/types'

/** Live backend calls of the candidate cabinet (contract PRD §8.1). */
export function fetchCandidateProfile() {
  return api.get('candidate/profile').json<CandidateSelf>()
}

export function putCandidateProfile(body: ProfileIn) {
  return api.put('candidate/profile', { json: body }).json<CandidateSelf>()
}

export function fetchCandidateGrade() {
  return api.get('candidate/grade').json<GradeInfo>()
}

export function fetchCandidateInvitations(status?: InvitationStatus) {
  return api
    .get('candidate/invitations', {
      searchParams: status ? { status } : undefined,
    })
    .json<InvitationCandidate[]>()
}

export function acceptInvitation(id: string) {
  return api.post(`candidate/invitations/${id}/accept`).json<InvitationAcceptOut>()
}

export function declineInvitation(id: string) {
  return api.post(`candidate/invitations/${id}/decline`).json<InvitationCandidate>()
}

/** Привязка ФСП ID вручную (автоматически — при входе через FSP ID) */
export function linkFsp(fspId: string) {
  return api.post('candidate/fsp-link', { json: { fsp_id: fspId } }).json<CandidateSelf>()
}

export function unlinkFsp() {
  return api.delete('candidate/fsp-link').json<CandidateSelf>()
}

// ── Resume (PRD §7.10) ───────────────────────────────────────────────
/**
 * PDF resume upload → LLM-parsed draft (multipart/form-data). The profile is
 * NOT changed server-side — the draft only prefills the editable form for a
 * mandatory human review. 422 = broken/not-a-PDF (readable detail).
 */
export function uploadResume(file: File) {
  const body = new FormData()
  body.append('file', file, file.name)
  return api.post('candidate/profile/resume', { body, timeout: 120_000 }).json<ResumeParseOut>()
}

/**
 * Generated standardized PDF profile. Authorized — must be fetched as a blob
 * through the ky instance (Bearer header), not via <img>/link.
 */
export function fetchProfilePdf() {
  return api.get('candidate/profile/pdf', { timeout: 60_000 }).blob()
}

// ── Tests (PRD §7.4) ─────────────────────────────────────────────────
export function startTestSession(gradeTarget: Grade, mode: TestMode = 'full') {
  // mode is proxied to core when the backend supports it; older deploys
  // silently ignore it and always run the full 10-question test.
  return api
    .post('tests/sessions', { json: { grade_target: gradeTarget, mode } })
    .json<TestSessionStarted>()
}

export function answerTest(sessionId: string, answer: string | number | null) {
  return api.post(`tests/sessions/${sessionId}/answers`, { json: { answer } }).json<TestAnswerOut>()
}
