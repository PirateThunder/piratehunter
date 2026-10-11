import type { Metadata, Viewport } from 'next'

export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:56151'

export const BASE_METADATA: Metadata = {
  metadataBase: new URL(SITE_URL),
  applicationName: 'PirateHunter',
  title: {
    default: 'PirateHunter — платформа, где работодатель находит вас сам',
    template: '%s — PirateHunter',
  },
  description:
    'Платформа-агрегатор ИТ-вакансий с обратной механикой: кандидаты категоризированы по специализации и подтверждённому тестом грейду, работодатель отправляет приглашение с зарплатной вилкой, контакты раскрываются только после принятия.',
}

export const BASE_VIEWPORT: Viewport = {
  themeColor: '#ffffff',
}
