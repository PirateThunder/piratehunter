import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

/** Empty placeholder block for lists/sections without data. */
export function EmptyState({
  icon: Icon,
  title,
  hint,
  action,
}: {
  icon: LucideIcon
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border px-6 py-10 text-center">
      <Icon className="size-8 text-placeholder" aria-hidden />
      <p className="font-medium text-heading">{title}</p>
      {hint && <p className="max-w-sm text-sm text-muted-foreground">{hint}</p>}
      {action}
    </div>
  )
}
