'use client'

import { cabinetApi } from '@/fsd/shared/api/cabinet-api'
import type { Grade, SalaryMarket, SpecSlug } from '@/fsd/shared/api/types'
import { formatRub } from '@/fsd/shared/lib/format'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { Skeleton } from '@/fsd/shared/ui/skeleton'

/*
 * «Вилка vs рынок по категории» (PRD §7.5.5): p25–p75 band + median marker
 * + the employer's own range marker. Honest empty state when the sample is
 * too small (null) or the endpoint is not deployed yet.
 */
export function SalaryMarketWidget({
  spec,
  grade,
  from,
  to,
}: {
  spec: SpecSlug | null
  grade: Grade | null
  from: number | null
  to: number | null
}) {
  const market = useQuery(
    () =>
      spec && grade ? cabinetApi.employer.getSalaryMarket(spec, grade) : Promise.resolve(null),
    [spec, grade],
  )

  if (!spec || !grade) {
    return (
      <p className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">
        Выберите специализацию и грейд — покажем рыночную вилку категории.
      </p>
    )
  }
  if (market.loading) return <Skeleton className="h-20 w-full" />

  const data = market.data
  if (!data || data.from_p25 == null || data.to_p75 == null) {
    return (
      <p className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">
        Данных по категории пока мало — рыночная вилка появится, когда на платформе будет больше
        приглашений и потребностей.
      </p>
    )
  }

  return <MarketBar market={data} from={from} to={to} />
}

function MarketBar({
  market,
  from,
  to,
}: {
  market: SalaryMarket
  from: number | null
  to: number | null
}) {
  const bandFrom = market.from_p25 ?? 0
  const bandTo = market.to_p75 ?? 0
  const median = market.from_p50 ?? market.to_p50 ?? null

  const yoursValid = from != null && to != null && from > 0 && to >= from
  const min = Math.min(bandFrom, yoursValid ? from : bandFrom) * 0.92
  const max = Math.max(bandTo, yoursValid ? (to ?? bandTo) : bandTo) * 1.08
  const span = max - min || 1
  const pct = (v: number) => `${Math.max(0, Math.min(100, ((v - min) / span) * 100))}%`

  const yourMedian = yoursValid ? (from + to) / 2 : null
  const belowMarket = yourMedian != null && median != null && yourMedian < median

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Вилка vs рынок категории
        </p>
        <p className="text-xs text-muted-foreground">
          выборка: {market.sample_needs + market.sample_invitations} · категория:{' '}
          {market.category_size}
        </p>
      </div>

      <div
        className="relative h-8"
        role="img"
        aria-label={`Рыночный коридор ${formatRub(bandFrom)} – ${formatRub(bandTo)}, медиана ${median ? formatRub(median) : '—'}`}
      >
        {/* p25–p75 band */}
        <div
          className="absolute top-1/2 h-3 -translate-y-1/2 rounded-pill bg-primary-soft"
          style={{ left: pct(bandFrom), width: `calc(${pct(bandTo)} - ${pct(bandFrom)})` }}
        />
        {/* median */}
        {median != null && (
          <div
            className="absolute top-1/2 h-5 w-0.5 -translate-y-1/2 rounded bg-primary"
            style={{ left: pct(median) }}
            title={`Медиана: ${formatRub(median)}`}
          />
        )}
        {/* your range */}
        {yoursValid && (
          <div
            className="absolute top-1/2 h-3 -translate-y-1/2 rounded-pill border-2 border-ink bg-transparent"
            style={{ left: pct(from), width: `calc(${pct(to)} - ${pct(from)})` }}
            title={`Ваша вилка: ${formatRub(from)} – ${formatRub(to)}`}
          />
        )}
      </div>

      <div className="flex justify-between font-mono text-xs text-muted-foreground tabular-nums">
        <span>{formatRub(Math.round(min))}</span>
        <span>медиана {median != null ? formatRub(median) : '—'}</span>
        <span>{formatRub(Math.round(max))}</span>
      </div>

      {yoursValid && median != null && (
        <p className={`text-xs ${belowMarket ? 'text-danger' : 'text-muted-foreground'}`}>
          {belowMarket
            ? 'Ваша вилка ниже медианы категории — отклик может быть слабее.'
            : 'Ваша вилка на уровне или выше медианы категории.'}
        </p>
      )}
    </div>
  )
}
