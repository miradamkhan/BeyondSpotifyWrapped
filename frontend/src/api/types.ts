export type TimelineGenrePoint = {
  genre: string
  percentage: number
  listen_ms: number
  listen_events: number
}

export type TimelineMonth = {
  month: string
  genres: TimelineGenrePoint[]
}

export type TimelineResponse = {
  months: TimelineMonth[]
  top_genres: string[]
}

export type ClusterLabel = {
  cluster_id: number
  label: string | null
  description: string | null
  representative_tracks: string[]
  representative_artists: string[]
}

export type ClusterPoint = {
  track_id: string
  name: string
  artists: string
  cluster_id: number
  x: number
  y: number
}

export type ClustersResponse = {
  clusters: ClusterLabel[]
  points: ClusterPoint[]
}

export type NeighborTrack = {
  track_id: string
  name: string
  artists: string
  similarity: number
  rank: number
}

export type MomentItem = {
  id: number
  month: string
  track_id: string
  track_name: string
  artists: string
  play_count: number
  total_ms: number
  listening_hours: number
  reason: string
  narrative: {
    title?: string
    month?: string
    note?: string
    sounds_like?: string[]
  } | null
  sounds_like: NeighborTrack[]
}

export type MomentsResponse = {
  moments: MomentItem[]
}

export type NarrativeItem = {
  source_key: string
  month: string | null
  model: string | null
  generated_at: string | null
  content: {
    title?: string
    date_range?: string
    narrative?: string
    referenced_genres?: string[]
    referenced_tracks?: string[]
  }
}

export type NarrativesResponse = {
  narratives: NarrativeItem[]
}

export type TasteDnaResponse = {
  model: string | null
  generated_at: string | null
  content: {
    headline?: string
    summary?: string
    core_genres?: string[]
    core_artists?: string[]
    major_shift_months?: string[]
  }
}

export type SyncResponse = {
  fetched: number
  inserted: number
  duplicates: number
}
