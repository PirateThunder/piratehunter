'use client'

import type { ReactNode } from 'react'

import { Toaster } from '@/fsd/shared/ui/sonner'

/** Client-side providers for the whole app. */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <Toaster />
    </>
  )
}
