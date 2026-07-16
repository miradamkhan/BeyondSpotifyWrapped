import type { NarrativesResponse } from '../api/types'
import { GlassPanel } from './GlassPanel'

type Props = {
  narratives: NarrativesResponse
}

export function ShiftsView({ narratives }: Props) {
  return (
    <div className="reveal h-full overflow-auto pr-1">
      <div className="mb-4">
        <p className="text-[10px] font-semibold tracking-[0.18em] text-[var(--color-accent)] uppercase">
          Change points
        </p>
        <h2 className="font-display text-3xl font-extrabold tracking-tight">Where the mix shifted</h2>
      </div>

      {narratives.narratives.length === 0 ? (
        <GlassPanel className="p-6 text-sm text-[var(--color-muted)]">
          No change-point narratives yet.
        </GlassPanel>
      ) : (
        <div className="space-y-4">
          {narratives.narratives.map((item) => (
            <GlassPanel key={item.source_key} strong className="p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-display text-lg font-bold text-[var(--color-accent)]">
                    {item.month || item.source_key}
                  </p>
                  <h3 className="font-display mt-1 text-2xl font-bold tracking-tight">
                    {item.content.title || 'Untitled shift'}
                  </h3>
                </div>
                {item.content.date_range ? (
                  <p className="rounded-full border border-[var(--color-line)] bg-white/5 px-3 py-1 text-[11px] text-[var(--color-muted)]">
                    {item.content.date_range}
                  </p>
                ) : null}
              </div>
              <p className="mt-4 max-w-4xl text-sm leading-relaxed text-[var(--color-muted)]">
                {item.content.narrative}
              </p>
              {(item.content.referenced_genres?.length ?? 0) > 0 ? (
                <p className="mt-4 text-xs text-[var(--color-ink)]">
                  Genres:{' '}
                  <span className="text-[var(--color-muted)]">
                    {item.content.referenced_genres?.join(' · ')}
                  </span>
                </p>
              ) : null}
            </GlassPanel>
          ))}
        </div>
      )}
    </div>
  )
}
