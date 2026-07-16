import type { MomentsResponse } from '../api/types'
import { GlassPanel } from './GlassPanel'

type Props = {
  moments: MomentsResponse
}

export function MomentsView({ moments }: Props) {
  return (
    <div className="reveal h-full overflow-auto pr-1">
      <div className="mb-4">
        <p className="text-[10px] font-semibold tracking-[0.18em] text-[var(--color-warm)] uppercase">
          Significant moments
        </p>
        <h2 className="font-display text-3xl font-extrabold tracking-tight">Songs that owned a month</h2>
      </div>

      {moments.moments.length === 0 ? (
        <GlassPanel className="p-6 text-sm text-[var(--color-muted)]">No moments yet.</GlassPanel>
      ) : (
        <div className="space-y-4">
          {moments.moments.map((moment) => (
            <GlassPanel key={moment.id} strong className="p-6">
              <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
                <div>
                  <p className="text-[11px] font-semibold tracking-[0.14em] text-[var(--color-accent)] uppercase">
                    {moment.month} · {moment.play_count} plays · {moment.listening_hours}h
                  </p>
                  <h3 className="font-display mt-2 text-2xl font-bold tracking-tight">
                    {moment.narrative?.title || moment.track_name}
                  </h3>
                  <p className="mt-1 text-sm text-[var(--color-muted)]">
                    {moment.track_name} — {moment.artists}
                  </p>
                  <p className="mt-4 text-sm leading-relaxed text-[var(--color-muted)]">
                    {moment.narrative?.note || moment.reason}
                  </p>
                </div>

                <div className="rounded-2xl border border-[var(--color-line)] bg-white/5 p-4">
                  <h4 className="text-[10px] font-semibold tracking-[0.16em] text-[var(--color-ink)] uppercase">
                    Sounds like
                  </h4>
                  {moment.sounds_like.length === 0 ? (
                    <p className="mt-3 text-sm text-[var(--color-muted)]">No neighbors</p>
                  ) : (
                    <ul className="mt-3 space-y-3">
                      {moment.sounds_like.map((neighbor) => (
                        <li key={`${moment.id}-${neighbor.track_id}`} className="text-sm">
                          <span className="font-semibold">{neighbor.name}</span>
                          <span className="text-[var(--color-muted)]">
                            {' '}
                            — {neighbor.artists}{' '}
                            <span className="text-[11px]">
                              ({(neighbor.similarity * 100).toFixed(0)}%)
                            </span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </GlassPanel>
          ))}
        </div>
      )}
    </div>
  )
}
