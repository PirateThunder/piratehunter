import {
  fetchCandidateGrade,
  fetchCandidateInvitations,
  fetchCandidateProfile,
} from '@/fsd/entities/candidate/api/candidate-api'
import {
  fetchCandidates,
  fetchCompany,
  fetchEmployerInvitations,
  fetchNeed,
  fetchNeeds,
  fetchSalaryMarket,
  fetchShortlist,
} from '@/fsd/entities/employer/api/employer-api'
import { env } from '@/fsd/shared/config/env'

import { type CabinetApi, mockApi } from './mock'
import type { Grade, SpecSlug } from './types'

/*
 * Cabinet data facade. Phase 2 default: live backend (entity APIs).
 * NEXT_PUBLIC_API_MOCK=1 switches to typed mock fixtures (offline dev).
 * Mutations and auth bypass the facade — they are always live
 * (features call the entity APIs in entities/<name>/api directly).
 */
const liveApi: CabinetApi = {
  candidate: {
    getProfile: () => fetchCandidateProfile(),
    getGrade: () => fetchCandidateGrade(),
    getInvitations: () => fetchCandidateInvitations(),
  },
  employer: {
    getCompany: () => fetchCompany(),
    getNeeds: () => fetchNeeds(),
    getNeed: (needId: string) => fetchNeed(needId),
    getShortlist: (needId: string) => fetchShortlist(needId),
    getCandidates: () => fetchCandidates(),
    getInvitations: () => fetchEmployerInvitations(),
    getSalaryMarket: (spec: SpecSlug, grade: Grade) => fetchSalaryMarket(spec, grade),
  },
}

export const cabinetApi: CabinetApi = env.apiMock ? mockApi : liveApi
