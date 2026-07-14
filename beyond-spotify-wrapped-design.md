# Beyond Spotify Wrapped — Updated System Design & Build Order

## Why this changed from the original plan
Spotify permanently deprecated the `audio-features` endpoint (Nov 2024), with no
replacement, and has continued shrinking API access since (Feb 2026 changelog
removed several more endpoints for new apps). The original design leaned on
energy/valence/acousticness/danceability for nearly everything — the timeline
chart, clustering, and Taste DNA. That data source no longer exists for new
developers. This doc reflects the redesigned architecture that works around
that constraint using metadata-based embeddings instead.

## Final architecture

| Layer | Decision | Why |
|---|---|---|
| Historical data | Spotify data export (full streaming history) | Only way to get real multi-year depth; API alone only returns last ~50 tracks |
| Ongoing data | `recently-played` API, nightly sync | Keeps data fresh after initial backfill |
| Track features | Text embeddings (sentence-transformers) on track/artist/genre metadata | Audio features are gone; metadata embeddings are a legitimate, defensible substitute |
| Clustering | PCA → ~40 dims → K-means | Avoids curse-of-dimensionality failure mode of clustering raw 384-dim embeddings |
| Visualization | UMAP → 2D, run separately from clustering | UMAP preserves local structure well for plotting but is too lossy to cluster on directly |
| Timeline chart | Genre-mix % by month (stacked area) | Replaces the old audio-feature line chart; computable directly from metadata |
| Change detection | PELT (ruptures library) on multivariate genre-mix vector | Real time-series ML instead of arbitrary thresholds; multivariate is more correct than per-genre |
| Narrative LLM | GPT-4o-mini, fed only pre-computed deltas from PELT, structured JSON output | Keeps the LLM doing writing, not analysis — avoids generic "your taste evolved" fluff |
| Vector DB | Chroma, single `find_nearest(vector, k)` primitive | Powers "sounds like" cross-era similarity — the one thing SQL genuinely can't answer |
| API auth | Simple API key via env var | Enough for a personal-scale project |

## Revised milestones

### Milestone 1 — Data foundation
- Request your full Spotify data export (privacy settings), parse the JSON dump
- Set up a Spotify developer app; confirm exactly which endpoints your access
  tier actually has (test directly — don't assume from docs)
- Design SQLite schema: `tracks`, `listen_events`, `sync_state`
- Build the export parser to backfill `listen_events`
- Build the `recently-played` sync job (APScheduler, nightly) for ongoing data
- Handle the overlap window between export and API data (dedup on track +
  timestamp within a tolerance) — figure out the exact merge logic once you
  see the real shapes of both data sources
- Milestone done when: 6+ months (or full history) of listens are in SQLite,
  export + live sync both flowing into the same tables without duplicates

### Milestone 2 — Embeddings, clustering, and change detection
- Build a text representation per track: e.g. `"{track} by {artist}, genres:
  {genres}, released {year}"`
- Embed all tracks with sentence-transformers (local, free)
- Store embeddings in Chroma
- Compute monthly genre-mix vectors (% of listening time per genre per month)
- Run PCA (→ ~40 dims) on track embeddings, then K-means (start k=5, tune)
- Run UMAP separately on the same embeddings, purely for 2D scatter plot
  coordinates — not used for clustering itself
- Run PELT change-point detection on the genre-mix time series to find real
  shift points, not arbitrary thresholds
- Milestone done when: you can plot clusters in matplotlib, and PELT reliably
  flags at least a couple of genuine, visually obvious shifts in your own
  listening history

### Milestone 3 — LLM narrative layer
- Write prompt templates: change-point narrative, cluster labeling,
  significant-moment notes, Taste DNA summary
- For narrative generation: feed the LLM only the pre-computed PELT deltas
  (e.g. "indie folk went from 4% to 31% between Jan–Apr"), not raw time
  series — this is the key guardrail against generic output
- Add explicit constraints in the prompt: reference specific artists/genres,
  reference specific date ranges, avoid vague language without a concrete
  example
- Integrate GPT-4o-mini, request structured JSON output (title, date range,
  narrative text, referenced genres/tracks)
- Build the `find_nearest(vector, k)` Chroma query and wire it into the
  significant-moments feature as "sounds like" — surfacing 3–5 nearest
  neighbor tracks from elsewhere in your history for a given moment/era
- Iterate on prompt quality manually before automating the weekly scheduler
- Store generated narratives in SQLite with timestamps

### Milestone 4 — FastAPI backend
- Endpoints:
  - `GET /timeline` — monthly genre-mix percentages
  - `GET /clusters` — cluster assignments + UMAP coordinates + LLM labels
  - `GET /moments` — significant replay moments + "sounds like" neighbors
  - `GET /narratives` — latest LLM-generated change-point narratives
  - `GET /taste-dna` — living profile
  - `POST /sync` — manual trigger for data sync
- Test all endpoints with curl/Postman
- Simple API key auth via env var

### Milestone 5 — React frontend
- Scaffold with Vite + React + Tailwind
- Timeline chart (Recharts, stacked area for genre mix)
- Cluster scatter plot (D3, using UMAP coordinates)
- Narrative cards + Taste DNA card
- Significant moments section, including "sounds like" neighbor tracks
- Connect all components to FastAPI backend
- Polish: loading states, empty states, responsive layout

### Milestone 6 — Cleanup and portfolio prep
- README with architecture diagram, setup instructions, screenshots —
  explicitly call out the audio-features deprecation and the redesign
  decision; this is a real engineering story worth telling, not just a
  footnote
- 2–3 minute demo video walking through your own data
- `sample_data/` folder with anonymized fake data so anyone can run it
  without Spotify credentials
- Deploy frontend to Vercel (free); backend local or free-tier Railway/Render
- Resume bullets (see below)

## Draft resume bullets (revise once built)
- Built an AI-powered music identity platform using metadata embeddings,
  PCA/K-means clustering, and change-point detection to generate personalized
  narrative insights about listening behavior evolution over time.
- Designed a semantic retrieval system (Chroma) surfacing cross-era track
  similarity, and engineered an LLM narrative pipeline that grounds GPT-4o-mini
  output in pre-computed statistical deltas rather than raw data, avoiding
  generic AI-generated summaries.
