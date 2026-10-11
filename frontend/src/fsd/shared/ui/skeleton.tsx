import type { ComponentProps } from 'react'

import { cn } from '@/fsd/shared/lib/utils'

function Skeleton({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden
      className={cn('animate-pulse rounded-lg bg-muted', className)}
      {...props}
    />
  )
}

export { Skeleton }
