import type { Role } from '@/fsd/shared/api/types'

/** Cabinet home per role. */
export const ROLE_HOME: Record<Role, string> = {
  candidate: '/candidate',
  employer: '/employer',
}
