import type { Metadata } from 'next'

import { EmployerNewNeedPage } from '@/fsd/pages/employer/employer-new-need-page'

export const metadata: Metadata = { title: 'Новая потребность' }

export default function NewNeed() {
  return <EmployerNewNeedPage />
}
