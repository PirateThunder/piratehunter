'use client'

import { type ReactNode, useId } from 'react'

import { cn } from '@/fsd/shared/lib/utils'

/** Labeled form field with a real label↔control association (a11y). */
export function Field({
  label,
  hint,
  className,
  children,
}: {
  label: string
  hint?: string
  className?: string
  children: (id: string) => ReactNode
}) {
  const id = useId()
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <label htmlFor={id} className="text-sm font-medium text-ink-2">
        {label}
      </label>
      {children(id)}
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  )
}
