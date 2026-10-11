import type { ReactNode } from 'react'

import { Providers } from '@/fsd/app/providers/providers'
import '@/fsd/app/styles/globals.css'

/**
 * Shared html/body shell for every root layout (the app has several:
 * the landing group, /login and the cabinet group). Fonts are self-hosted
 * via @font-face in globals.css; client providers live in Providers.
 * Light theme only (PRD) — no anti-FOUC theme script needed.
 */
export function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="ru" suppressHydrationWarning className="h-full antialiased">
      <body className="min-h-full">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
