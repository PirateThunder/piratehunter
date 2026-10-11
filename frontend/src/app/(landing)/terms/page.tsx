import type { Metadata } from 'next'

import { LegalPage } from '@/fsd/widgets/legal/legal-page'

export const metadata: Metadata = { title: 'Условия использования' }

export default function Terms() {
  return <LegalPage title="Условия использования" />
}
