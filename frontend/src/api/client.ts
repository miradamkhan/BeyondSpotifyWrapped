import type {
  ClustersResponse,
  MomentsResponse,
  NarrativesResponse,
  SyncResponse,
  TasteDnaResponse,
  TimelineResponse,
} from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
const API_KEY = import.meta.env.VITE_API_KEY ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_KEY) {
    throw new Error('VITE_API_KEY is missing. Copy frontend/.env.example to .env.')
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'X-API-Key': API_KEY,
      ...(init?.headers ?? {}),
    },
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`${response.status} ${path}: ${detail || response.statusText}`)
  }

  return response.json() as Promise<T>
}

export const api = {
  timeline: () => request<TimelineResponse>('/timeline'),
  clusters: () => request<ClustersResponse>('/clusters'),
  moments: () => request<MomentsResponse>('/moments'),
  narratives: () => request<NarrativesResponse>('/narratives'),
  tasteDna: () => request<TasteDnaResponse>('/taste-dna'),
  sync: () =>
    request<SyncResponse>('/sync', {
      method: 'POST',
    }),
}
