import { cn } from '@/fsd/shared/lib/utils'

/** ФСП logo from the брендбук (post-hackathon: swap files in /public/brand).
 *  NB: «w» in the brandbook means "for WHITE background" (dark wordmark);
 *  the plain logo_01.svg has a light wordmark for dark backgrounds. */
export function Logo({
  variant = 'color',
  className,
}: {
  variant?: 'color' | 'white'
  className?: string
}) {
  const src = variant === 'white' ? '/brand/logo_01.svg' : '/brand/logo_01w.svg'
  return (
    // biome-ignore lint/performance/noImgElement: brand SVG, next/image optimization unnecessary
    <img
      src={src}
      alt="Федерация спортивного программирования"
      className={cn('h-8 w-auto', className)}
    />
  )
}
