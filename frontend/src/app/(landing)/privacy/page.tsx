import type { Metadata } from 'next'

import { LegalPage } from '@/fsd/widgets/legal/legal-page'

export const metadata: Metadata = { title: 'Политика конфиденциальности' }

export default function Privacy() {
  return <LegalPage title="Политика конфиденциальности" />
}
