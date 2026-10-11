import type { Metadata } from 'next'

import { CandidatePage } from '@/fsd/pages/candidate/candidate-page'

export const metadata: Metadata = { title: 'Кабинет кандидата' }

export default function Candidate() {
  return <CandidatePage />
}
