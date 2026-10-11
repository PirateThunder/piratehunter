'use client'

import { Toaster as SonnerToaster } from 'sonner'

/** App-wide toaster (light theme only per PRD). */
function Toaster() {
  return (
    <SonnerToaster
      theme="light"
      position="bottom-right"
      toastOptions={{
        style: {
          background: 'var(--popover)',
          color: 'var(--popover-foreground)',
          border: '1px solid var(--border)',
        },
      }}
    />
  )
}

export { Toaster }
export { toast } from 'sonner'
