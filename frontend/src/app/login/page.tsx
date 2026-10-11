import type { Metadata } from 'next'

import { LoginPage } from '@/fsd/pages/login/login-page'

export const metadata: Metadata = { title: 'Вход' }

export default function Login() {
  return <LoginPage />
}
