import type { Metadata } from 'next'
import type { ReactNode } from 'react'

import { BASE_METADATA, BASE_VIEWPORT } from '@/fsd/app/metadata'
import { RootShell } from '@/fsd/app/root-shell'
import { AuthGate } from '@/fsd/features/auth/auth-gate'
import { AppChrome } from '@/fsd/widgets/chrome/app-chrome'

export const metadata: Metadata = { ...BASE_METADATA }
export const viewport = BASE_VIEWPORT

// Root layout of the cabinet group: auth guard + chrome (header with logo,
// role badge and logout). Route groups don't get their own LayoutProps entry
// (the group shares path "/"), so children are typed inline.
export default function AppRootLayout({ children }: { children: ReactNode }) {
  return (
    <RootShell>
      <AuthGate>
        <AppChrome>{children}</AppChrome>
      </AuthGate>
    </RootShell>
  )
}
