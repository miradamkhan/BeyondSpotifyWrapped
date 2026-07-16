import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { TimelineResponse } from '../api/types'
import { GlassPanel } from './GlassPanel'

const PALETTE = [
  '#3dd6a5',
  '#ff8f5a',
  '#7ec8ff',
  '#e8c547',
  '#9b8cff',
  '#5ad0c8',
  '#ff6b8a',
  '#8fd14f',
  '#f0a06a',
  '#6aa8ff',
  '#d4a373',
  '#80ed99',
]

type Props = {
  timeline: TimelineResponse
  height?: number
}

export function TimelineChart({ timeline, height = 280 }: Props) {
  if (timeline.months.length === 0) {
    return (
      <GlassPanel strong className="flex h-full items-center justify-center p-6">
        <p className="text-sm text-[var(--color-muted)]">No timeline data yet.</p>
      </GlassPanel>
    )
  }

  const chartData = timeline.months.map((month) => {
    const row: Record<string, string | number> = { month: month.month }
    for (const genre of timeline.top_genres) {
      const match = month.genres.find((item) => item.genre === genre)
      row[genre] = Number(((match?.percentage ?? 0) * 100).toFixed(2))
    }
    return row
  })

  return (
    <GlassPanel strong className="flex h-full flex-col p-5">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold tracking-[0.18em] text-[var(--color-accent)] uppercase">
            Timeline
          </p>
          <h3 className="font-display text-xl font-bold">Genre mix over time</h3>
        </div>
        <p className="text-xs text-[var(--color-muted)]">{timeline.months.length} months</p>
      </div>
      <div className="min-h-0 flex-1" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgb(232 242 236 / 0.08)" vertical={false} />
            <XAxis
              dataKey="month"
              tick={{ fill: '#9bb0a3', fontSize: 10 }}
              tickMargin={8}
              minTickGap={32}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#9bb0a3', fontSize: 10 }}
              tickFormatter={(value: number) => `${value}%`}
              width={36}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: 'rgb(8 28 20 / 0.92)',
                border: '1px solid rgb(232 242 236 / 0.16)',
                borderRadius: 16,
                color: '#e8f2ec',
                backdropFilter: 'blur(12px)',
              }}
              formatter={(value) => [`${Number(value ?? 0).toFixed(1)}%`, '']}
            />
            <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8, color: '#9bb0a3' }} />
            {timeline.top_genres.map((genre, index) => (
              <Area
                key={genre}
                type="monotone"
                dataKey={genre}
                stackId="1"
                stroke={PALETTE[index % PALETTE.length]}
                fill={PALETTE[index % PALETTE.length]}
                fillOpacity={0.55}
                strokeWidth={1.2}
                isAnimationActive
                animationDuration={900}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </GlassPanel>
  )
}
