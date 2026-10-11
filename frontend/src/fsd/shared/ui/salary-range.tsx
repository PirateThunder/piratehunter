import type { SalaryType } from '@/fsd/shared/api/types'
import { formatSalary, salaryTypeLabel } from '@/fsd/shared/lib/format'
import { cn } from '@/fsd/shared/lib/utils'

/** Salary range in mono figures; gross/net always labeled (ТЗ §2.2). */
export function SalaryRange({
  from,
  to,
  type,
  size = 'md',
  className,
}: {
  from: number
  to: number
  type: SalaryType
  size?: 'md' | 'lg'
  className?: string
}) {
  return (
    <div className={cn('flex flex-col', className)}>
      <span
        className={cn(
          'font-mono font-semibold text-ink tabular-nums',
          size === 'lg' ? 'text-2xl' : 'text-base',
        )}
      >
        {formatSalary(from, to)}
      </span>
      <span className="text-xs text-muted-foreground">{salaryTypeLabel(type)}</span>
    </div>
  )
}
