import { fetchMe } from '@/fsd/entities/session/api/auth-api'
import { useSession } from '@/fsd/entities/session/model/session-store'
import { refreshSession } from '@/fsd/shared/api/http'

/**
 * Session restore on app entry: the in-memory access token is gone after a
 * reload, so we exchange the httpOnly refresh cookie for a fresh token and
 * load the profile. Ends in either status 'auth' or 'guest'.
 */
export async function bootstrapSession(): Promise<void> {
  const session = useSession.getState()
  if (session.status === 'auth') return
  if (!(await refreshSession())) return // refreshSession already marked us guest
  try {
    const user = await fetchMe()
    useSession.setState({ user, status: 'auth' })
  } catch {
    useSession.getState().setGuest()
  }
}
