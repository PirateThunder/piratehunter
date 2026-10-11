import type { Metadata } from 'next'

import { CandidateTestPage } from '@/fsd/pages/candidate/candidate-test-page'

export const metadata: Metadata = { title: 'Тест на грейд' }

export default function CandidateTest() {
  return <CandidateTestPage />
}
