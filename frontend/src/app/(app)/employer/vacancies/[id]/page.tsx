import type { Metadata } from 'next'

import { EmployerVacancyPage } from '@/fsd/pages/employer/employer-vacancy-page'

export const metadata: Metadata = { title: 'Вакансия' }

export default async function Vacancy({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <EmployerVacancyPage vacancyId={id} />
}
