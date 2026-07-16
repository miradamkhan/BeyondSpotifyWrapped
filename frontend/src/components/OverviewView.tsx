import type { AnalyticsData } from '../hooks/useAnalytics'
import { ClusterChart } from './ClusterChart'
import { GlassPanel } from './GlassPanel'
import { TimelineChart } from './TimelineChart'

type Props = {
  data: AnalyticsData
}

export function OverviewView({ data }: Props) {
  const { tasteDna, timeline, clusters } = data

  return (
    <div className="reveal flex h-full flex-col gap-4 overflow-hidden">
      <GlassPanel strong className="shrink-0 p-6">
        <div className="flex items-end justify-between gap-6">
          <div className="max-w-3xl">
            <p className="text-[10px] font-semibold tracking-[0.2em] text-[var(--color-accent)] uppercase">
              Now playing your history
            </p>
            <h2 className="font-display mt-2 text-3xl leading-tight font-extrabold tracking-tight xl:text-4xl">
              {tasteDna.content.headline || 'Your listening archive'}
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[var(--color-muted)] xl:text-base">
              {tasteDna.content.summary ||
                'Genre timelines, semantic clusters, and grounded narratives from your full Spotify export.'}
            </p>
          </div>
          <div className="hidden shrink-0 grid-cols-2 gap-3 xl:grid">
            <Stat label="Months" value={String(timeline.months.length)} />
            <Stat label="Tracks" value={String(clusters.points.length)} />
          </div>
        </div>
      </GlassPanel>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-2">
        <TimelineChart timeline={timeline} height={300} />
        <ClusterChart clusters={clusters} compact />
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--color-line)] bg-white/5 px-4 py-3 text-right">
      <p className="text-[10px] tracking-[0.16em] text-[var(--color-muted)] uppercase">{label}</p>
      <p className="font-display text-2xl font-bold">{value}</p>
    </div>
  )
}
