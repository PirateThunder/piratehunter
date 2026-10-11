import type { Metadata } from 'next'

import { SITE_URL } from '@/fsd/app/metadata'
import { LandingPage } from '@/fsd/pages/landing/landing-page'

export const metadata: Metadata = {
  title: 'PirateHunter — работодатель находит вас сам',
  description:
    'Платформа-агрегатор ИТ-вакансий с обратной механикой: категоризированная база кандидатов (специализация × подтверждённый тестом грейд), объяснимая подборка, приглашения с обязательной зарплатной вилкой. Контакты скрыты до принятия.',
  alternates: { canonical: SITE_URL },
  openGraph: {
    type: 'website',
    url: SITE_URL,
    siteName: 'PirateHunter',
    title: 'PirateHunter — работодатель находит вас сам',
    description:
      'Обратная механика поиска: работодатель сам находит кандидатов и шлёт приглашение с вилкой ЗП. Контакты раскрываются после принятия.',
    locale: 'ru_RU',
  },
}

export default function Home() {
  return <LandingPage />
}
