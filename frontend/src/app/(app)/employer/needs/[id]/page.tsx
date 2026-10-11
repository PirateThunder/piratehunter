import type { Metadata } from 'next'

import { EmployerNeedPage } from '@/fsd/pages/employer/employer-need-page'

export const metadata: Metadata = { title: 'Потребность и подборка' }

export default function Need({ params }: { params: Promise<{ id: string }> }) {
  return <EmployerNeedPage params={params} />
}
