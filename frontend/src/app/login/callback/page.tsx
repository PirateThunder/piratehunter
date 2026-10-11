import type { Metadata } from 'next'

import { LoginCallbackPage } from '@/fsd/pages/login/login-callback-page'

export const metadata: Metadata = { title: 'Вход через FSP ID' }

export default function LoginCallback() {
  return <LoginCallbackPage />
}
