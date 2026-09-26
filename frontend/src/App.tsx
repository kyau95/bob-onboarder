import { useState } from 'react'
import { GraphCanvas } from './components/GraphCanvas'
import { ImpactPanel } from './components/ImpactPanel'
import { RepoIngestForm } from './components/RepoIngestForm'
import { Sidebar } from './components/Sidebar'

export default function App() {
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null)
  const [graphRefreshKey, setGraphRefreshKey] = useState(0)
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0)
  const [highlightedNodeIds, setHighlightedNodeIds] = useState<Set<string>>(new Set())

  function refreshSidebar() {
    setSidebarRefreshKey(k => k + 1)
  }

  function handleRepoReady(repoId: string) {
    setSelectedRepoId(repoId)
    setHighlightedNodeIds(new Set())
    // Bump the key to force GraphCanvas to re-fetch even if repoId didn't change
    setGraphRefreshKey(k => k + 1)
    // Reload sidebar so the completed repository shows analyzed / done
    refreshSidebar()
  }

  function handleIngestStarted(repoId: string) {
    setSelectedRepoId(repoId)
    refreshSidebar()
  }

  function handleSelect(repoId: string) {
    setSelectedRepoId(repoId)
    setHighlightedNodeIds(new Set())
    setGraphRefreshKey(k => k + 1)
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-gray-50 font-sans">
      {/* ── Left sidebar ─────────────────────────────────────────────── */}
      <aside className="flex flex-col w-72 shrink-0 border-r border-gray-200 bg-white">
        {/* Header */}
        <div className="px-4 py-4 border-b border-gray-200">
          <h1 className="text-base font-bold text-gray-900 leading-tight">
            Bob the Onboarder
          </h1>
          <p className="text-xs text-gray-400 mt-0.5">Repository intelligence</p>
        </div>

        {/* Ingest form */}
        <div className="px-4 py-3 border-b border-gray-100">
          <RepoIngestForm
            onReady={handleRepoReady}
            onIngestStarted={handleIngestStarted}
            onStatusChange={refreshSidebar}
          />
        </div>

        {/* Repo list */}
        <div className="flex-1 min-h-0">
          <Sidebar
            selectedId={selectedRepoId}
            refreshKey={sidebarRefreshKey}
            onSelect={handleSelect}
          />
        </div>

        {/* Impact panel (only when a repo is selected + graph loaded) */}
        {selectedRepoId && (
          <div className="border-t border-gray-200 px-4 py-4 overflow-y-auto max-h-80">
            <ImpactPanel
              repoId={selectedRepoId}
              onHighlight={setHighlightedNodeIds}
            />
          </div>
        )}
      </aside>

      {/* ── Main graph canvas ─────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0">
        {selectedRepoId ? (
          <GraphCanvas
            repoId={selectedRepoId}
            refreshKey={graphRefreshKey}
            highlightedNodeIds={highlightedNodeIds}
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-gray-400">
            <svg
              className="w-16 h-16 text-gray-200"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1}
            >
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
            <p className="text-sm">Ingest a repository to visualise its architecture</p>
          </div>
        )}
      </main>
    </div>
  )
}
