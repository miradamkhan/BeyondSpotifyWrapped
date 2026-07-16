import { useEffect, useMemo, useRef, useState } from 'react'
import * as d3 from 'd3'
import type { ClustersResponse } from '../api/types'
import { GlassPanel } from './GlassPanel'

const COLORS = [
  '#3dd6a5',
  '#ff8f5a',
  '#7ec8ff',
  '#e8c547',
  '#9b8cff',
  '#5ad0c8',
  '#ff6b8a',
  '#8fd14f',
]

type Props = {
  clusters: ClustersResponse
  compact?: boolean
}

export function ClusterChart({ clusters, compact = false }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [activeCluster, setActiveCluster] = useState<number | null>(null)

  const sampledPoints = useMemo(() => {
    if (clusters.points.length <= 2500) return clusters.points
    return clusters.points.filter((_, index) => index % 3 === 0)
  }, [clusters.points])

  useEffect(() => {
    const svg = svgRef.current
    if (!svg || sampledPoints.length === 0) return

    const width = svg.clientWidth || 700
    const height = compact ? 260 : 320
    const margin = { top: 12, right: 12, bottom: 12, left: 12 }

    const xs = sampledPoints.map((point) => point.x)
    const ys = sampledPoints.map((point) => point.y)
    const x = d3
      .scaleLinear()
      .domain(d3.extent(xs) as [number, number])
      .nice()
      .range([margin.left, width - margin.right])
    const y = d3
      .scaleLinear()
      .domain(d3.extent(ys) as [number, number])
      .nice()
      .range([height - margin.bottom, margin.top])

    const root = d3.select(svg)
    root.selectAll('*').remove()
    root.attr('viewBox', `0 0 ${width} ${height}`)

    const points = root
      .append('g')
      .selectAll('circle')
      .data(sampledPoints)
      .join('circle')
      .attr('cx', (d) => x(d.x))
      .attr('cy', (d) => y(d.y))
      .attr('r', 0)
      .attr('fill', (d) => COLORS[d.cluster_id % COLORS.length])
      .attr('fill-opacity', (d) =>
        activeCluster === null || d.cluster_id === activeCluster ? 0.8 : 0.1,
      )

    points
      .transition()
      .duration(650)
      .delay((_, index) => Math.min(index * 0.35, 350))
      .attr('r', compact ? 2.1 : 2.5)

    points.append('title').text((d) => `${d.name} — ${d.artists}`)
  }, [sampledPoints, activeCluster, compact])

  if (clusters.points.length === 0) {
    return (
      <GlassPanel strong className="flex h-full items-center justify-center p-6">
        <p className="text-sm text-[var(--color-muted)]">No cluster data yet.</p>
      </GlassPanel>
    )
  }

  return (
    <GlassPanel strong className="flex h-full flex-col p-5">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold tracking-[0.18em] text-[var(--color-warm)] uppercase">
            Clusters
          </p>
          <h3 className="font-display text-xl font-bold">Tracks in semantic space</h3>
        </div>
        <p className="text-xs text-[var(--color-muted)]">{clusters.points.length} tracks</p>
      </div>

      <div className="mb-3 flex flex-wrap gap-1.5">
        <FilterChip
          active={activeCluster === null}
          label="All"
          onClick={() => setActiveCluster(null)}
        />
        {clusters.clusters.map((cluster) => (
          <FilterChip
            key={cluster.cluster_id}
            active={activeCluster === cluster.cluster_id}
            label={cluster.label || `C${cluster.cluster_id}`}
            color={COLORS[cluster.cluster_id % COLORS.length]}
            onClick={() => setActiveCluster(cluster.cluster_id)}
          />
        ))}
      </div>

      <svg
        ref={svgRef}
        className={`w-full ${compact ? 'h-[260px]' : 'h-[320px]'}`}
        role="img"
        aria-label="Track cluster scatter plot"
      />

      {!compact ? (
        <div className="mt-3 grid max-h-[120px] grid-cols-2 gap-3 overflow-auto">
          {clusters.clusters.map((cluster) => (
            <div key={cluster.cluster_id} className="rounded-xl bg-white/5 px-3 py-2">
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: COLORS[cluster.cluster_id % COLORS.length] }}
                />
                <p className="truncate text-xs font-semibold">
                  {cluster.label || `Cluster ${cluster.cluster_id}`}
                </p>
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] text-[var(--color-muted)]">
                {cluster.description || 'No label'}
              </p>
            </div>
          ))}
        </div>
      ) : null}
    </GlassPanel>
  )
}

function FilterChip({
  active,
  label,
  color,
  onClick,
}: {
  active: boolean
  label: string
  color?: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
        active
          ? 'bg-[var(--color-accent)] text-[#04110c]'
          : 'border border-[var(--color-line)] bg-white/5 text-[var(--color-muted)] hover:text-[var(--color-ink)]'
      }`}
      style={active && color ? { background: color, color: '#04110c' } : undefined}
    >
      {label}
    </button>
  )
}
