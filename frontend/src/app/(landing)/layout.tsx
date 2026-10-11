import type { Metadata } from 'next'

import { BASE_METADATA, BASE_VIEWPORT } from '@/fsd/app/metadata'
import { RootShell } from '@/fsd/app/root-shell'

export const metadata: Metadata = { ...BASE_METADATA }
export const viewport = BASE_VIEWPORT

// Root layout of the landing group (one of several root layouts — /login and
// the cabinet group have their own). Public marketing pages only.
export default function LandingRootLayout({ children }: LayoutProps<'/'>) {
  return <RootShell>{children}</RootShell>
}
