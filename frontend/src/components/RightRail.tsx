import type { MomentItem, NarrativeItem, TasteDnaResponse } from '../api/types'
import { GlassPanel } from './GlassPanel'

type RightRailProps = {
  tasteDna: TasteDnaResponse
  narratives: NarrativeItem[]
  topMoment: MomentItem | null
}

export function RightRail({ tasteDna, narratives, topMoment }: RightRailProps) {
  const content = tasteDna.content

  return (
    <aside className="flex h-full w-[300px] shrink-0 flex-col gap-4 overflow-hidden">
      <GlassPanel strong className="p-5">
        <p className="text-[10px] font-semibold tracking-[0.18em] text-[var(--color-accent)] uppercase">
          Taste DNA
        </p>
        <h2 className="font-display mt-2 text-xl leading-tight font-bold">
          {content.headline || 'Your listening profile'}
        </h2>
        <p className="mt-3 line-clamp-5 text-sm leading-relaxed text-[var(--color-muted)]">
          {content.summary || 'Generate narratives to fill this panel.'}
        </p>
      </GlassPanel>

      <GlassPanel className="flex-1 overflow-auto p-5">
        <p className="text-[10px] font-semibold tracking-[0.18em] text-[var(--color-muted)] uppercase">
          Core genres
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {(content.core_genres ?? []).slice(0, 8).map((genre) => (
            <span
              key={genre}
              className="rounded-full border border-[var(--color-line)] bg-white/5 px-2.5 py-1 text-[11px] font-medium"
            >
              {genre}
            </span>
          ))}
          {(content.core_genres ?? []).length === 0 ? (
            <span className="text-sm text-[var(--color-muted)]">None yet</span>
          ) : null}
        </div>

        <p className="mt-6 text-[10px] font-semibold tracking-[0.18em] text-[var(--color-muted)] uppercase">
          Shift months
        </p>
        <ul className="mt-3 space-y-2">
          {narratives.slice(0, 6).map((item) => (
            <li
              key={item.source_key}
              className="flex items-center justify-between rounded-xl bg-white/5 px-3 py-2 text-sm"
            >
              <span className="font-semibold text-[var(--color-accent)]">
                {item.month || item.source_key}
              </span>
              <span className="max-w-[140px] truncate text-[11px] text-[var(--color-muted)]">
                {item.content.title}
              </span>
            </li>
          ))}
        </ul>
      </GlassPanel>

      <GlassPanel className="p-5">
        <p className="text-[10px] font-semibold tracking-[0.18em] text-[var(--color-warm)] uppercase">
          Top replay moment
        </p>
        {topMoment ? (
          <>
            <h3 className="font-display mt-2 text-lg leading-tight font-bold">
              {topMoment.track_name}
            </h3>
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              {topMoment.artists} · {topMoment.month}
            </p>
            <p className="mt-3 text-sm text-[var(--color-ink)]">
              {topMoment.play_count} plays · {topMoment.listening_hours}h
            </p>
          </>
        ) : (
          <p className="mt-2 text-sm text-[var(--color-muted)]">No moments yet</p>
        )}
      </GlassPanel>
    </aside>
  )
}
