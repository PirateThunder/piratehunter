import type { Metadata } from 'next'

import { EmployerVacanciesPage } from '@/fsd/pages/employer/employer-vacancies-page'

export const metadata: Metadata = { title: 'Вакансии' }

export default function Vacancies() {
  return <EmployerVacanciesPage />
}
