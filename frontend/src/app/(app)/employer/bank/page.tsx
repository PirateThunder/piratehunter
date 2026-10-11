import type { Metadata } from 'next'

import { EmployerBankPage } from '@/fsd/pages/employer/employer-bank-page'

export const metadata: Metadata = { title: 'Банк кандидатов' }

export default function Bank() {
  return <EmployerBankPage />
}
