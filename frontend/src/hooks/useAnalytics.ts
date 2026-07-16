import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type {
  ClustersResponse,
  MomentsResponse,
  NarrativesResponse,
  TasteDnaResponse,
  TimelineResponse,
} from '../api/types'

export type AnalyticsData = {
  timeline: TimelineResponse
  clusters: ClustersResponse
  moments: MomentsResponse
  narratives: NarrativesResponse
  tasteDna: TasteDnaResponse
}

type AnalyticsState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: AnalyticsData }

export function useAnalytics(): AnalyticsState {
  const [state, setState] = useState<AnalyticsState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [timeline, clusters, moments, narratives, tasteDna] = await Promise.all([
          api.timeline(),
          api.clusters(),
          api.moments(),
          api.narratives(),
          api.tasteDna(),
        ])
        if (!cancelled) {
          setState({
            status: 'ready',
            data: { timeline, clusters, moments, narratives, tasteDna },
          })
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            status: 'error',
            message: error instanceof Error ? error.message : 'Failed to load analytics',
          })
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
