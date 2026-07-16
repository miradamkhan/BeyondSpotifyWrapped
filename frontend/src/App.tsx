import { useState } from 'react'
import { api } from './api/client'
import { MomentsView } from './components/MomentsView'
import { OverviewView } from './components/OverviewView'
import { RightRail } from './components/RightRail'
import { ShiftsView } from './components/ShiftsView'
import { Sidebar, type DashboardView } from './components/Sidebar'
import { TasteView } from './components/TasteView'
import { useAnalytics } from './hooks/useAnalytics'

export default function App() {
  const state = useAnalytics()
  const [view, setView] = useState<DashboardView>('overview')
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)

  async function handleSync() {
    setSyncing(true)
    setSyncMessage(null)
    try {
      const result = await api.sync()
      setSyncMessage(
        `Fetched ${result.fetched} · inserted ${result.inserted} · dupes ${result.duplicates}`,
      )
    } catch (error) {
      setSyncMessage(error instanceof Error ? error.message : 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  if (state.status === 'loading') {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="atmosphere" />
        <p className="font-display relative z-10 text-2xl font-bold">Loading archive…</p>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="flex h-full items-center justify-center px-8">
        <div className="atmosphere" />
        <div className="glass relative z-10 max-w-lg rounded-3xl p-8">
          <h1 className="font-display text-3xl font-bold">Couldn’t reach the API</h1>
          <p className="mt-4 text-[var(--color-muted)]">{state.message}</p>
          <p className="mt-3 text-sm text-[var(--color-muted)]">
            Start the FastAPI server on port 8000 and check <code>frontend/.env</code>.
          </p>
        </div>
      </div>
    )
  }

  const { moments, narratives, tasteDna } = state.data

  return (
    <div className="relative h-full p-4">
      <div className="atmosphere" />
      <div className="relative z-10 flex h-full gap-4">
        <Sidebar
          active={view}
          onChange={setView}
          onSync={() => {
            void handleSync()
          }}
          syncing={syncing}
          syncMessage={syncMessage}
        />

        <main className="min-w-0 flex-1 overflow-hidden">
          {view === 'overview' ? <OverviewView data={state.data} /> : null}
          {view === 'taste' ? <TasteView tasteDna={tasteDna} /> : null}
          {view === 'shifts' ? <ShiftsView narratives={narratives} /> : null}
          {view === 'moments' ? <MomentsView moments={moments} /> : null}
        </main>

        <RightRail
          tasteDna={tasteDna}
          narratives={narratives.narratives}
          topMoment={moments.moments[0] ?? null}
        />
      </div>
    </div>
  )
}
