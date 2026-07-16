export type DashboardView = 'overview' | 'taste' | 'shifts' | 'moments'

const NAV: { id: DashboardView; label: string; hint: string }[] = [
  { id: 'overview', label: 'Overview', hint: 'Charts' },
  { id: 'taste', label: 'Taste DNA', hint: 'Profile' },
  { id: 'shifts', label: 'Shifts', hint: 'Change points' },
  { id: 'moments', label: 'Moments', hint: 'Replays' },
]

type SidebarProps = {
  active: DashboardView
  onChange: (view: DashboardView) => void
  onSync: () => void
  syncing: boolean
  syncMessage: string | null
}

export function Sidebar({ active, onChange, onSync, syncing, syncMessage }: SidebarProps) {
  return (
    <aside className="glass flex h-full w-[240px] shrink-0 flex-col rounded-[28px] p-5">
      <div>
        <p className="font-display text-[11px] font-bold tracking-[0.22em] text-[var(--color-accent)] uppercase">
          Archive
        </p>
        <h1 className="font-display mt-2 text-2xl leading-none font-extrabold tracking-tight">
          Beyond
          <br />
          Spotify
          <br />
          Wrapped
        </h1>
      </div>

      <nav className="mt-10 flex flex-1 flex-col gap-1.5">
        <p className="mb-2 text-[10px] font-semibold tracking-[0.18em] text-[var(--color-muted)] uppercase">
          Navigate
        </p>
        {NAV.map((item) => {
          const isActive = item.id === active
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={`rounded-2xl px-3.5 py-3 text-left transition ${
                isActive
                  ? 'bg-[var(--color-accent)] text-[#04110c] shadow-[0_8px_24px_rgb(61_214_165_/_0.35)]'
                  : 'text-[var(--color-ink)] hover:bg-white/5'
              }`}
            >
              <span className="block text-sm font-semibold">{item.label}</span>
              <span
                className={`block text-[11px] ${isActive ? 'text-[#04110c]/70' : 'text-[var(--color-muted)]'}`}
              >
                {item.hint}
              </span>
            </button>
          )
        })}
      </nav>

      <div className="mt-auto space-y-3 border-t border-[var(--color-line)] pt-4">
        <button
          type="button"
          onClick={onSync}
          disabled={syncing}
          className="w-full rounded-2xl border border-[var(--color-line)] bg-white/5 px-3.5 py-3 text-sm font-semibold transition hover:border-[var(--color-accent)] hover:bg-white/10 disabled:opacity-60"
        >
          {syncing ? 'Syncing…' : 'Sync recent plays'}
        </button>
        {syncMessage ? (
          <p className="text-[11px] leading-snug text-[var(--color-muted)]">{syncMessage}</p>
        ) : (
          <p className="text-[11px] text-[var(--color-muted)]">Local personal archive</p>
        )}
      </div>
    </aside>
  )
}
