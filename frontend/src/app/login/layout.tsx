import type { Metadata } from 'next'

import { BASE_METADATA, BASE_VIEWPORT } from '@/fsd/app/metadata'
import { RootShell } from '@/fsd/app/root-shell'

export const metadata: Metadata = { ...BASE_METADATA }
export const viewport = BASE_VIEWPORT

// Root layout of the auth group: bare shell without site chrome.
export default function LoginRootLayout({ children }: LayoutProps<'/login'>) {
  return <RootShell>{children}</RootShell>
}
