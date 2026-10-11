import type { Metadata } from 'next'

import { EmployerPage } from '@/fsd/pages/employer/employer-page'

export const metadata: Metadata = { title: 'Кабинет работодателя' }

export default function Employer() {
  return <EmployerPage />
}
