// RepoIngestForm — URL input form with inline status badge and pipeline trigger

import { useEffect, useRef, useState } from 'react'
import { ingestRepo, triggerAnalyze, triggerGraphBuild } from '../api'
import { useRepoPolling } from '../useRepoPolling'
import type { RepoStatus } from '../types'

interface Props {
  onReady: (repoId: string) => void
}

const STATUS_COLOR: Record<RepoStatus, string> = {
  pending:   'bg-gray-200 text-gray-600',
  cloning:   'bg-yellow-100 text-yellow-700',
  ready:     'bg-blue-100 text-blue-700',
  analyzing: 'bg-yellow-100 text-yellow-700',
  analyzed:  'bg-green-100 text-green-700',
  error:     'bg-red-100 text-red-700',
}

export function RepoIngestForm({ onReady }: Props) {
  const [url, setUrl]         = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const { repo, polling, startPolling, stopPolling } = useRepoPolling()

  // Track which status we've already acted on to avoid double-firing
  // key: `${repo_id}:${status}`
  const actedRef = useRef(new Set<string>())

  useEffect(() => {
    if (!repo) return

    const { repo_id, status } = repo
    const key = `${repo_id}:${status}`
    if (actedRef.current.has(key)) return

    if (status === 'ready') {
      actedRef.current.add(key)
      void triggerAnalyze(repo_id)
    } else if (status === 'analyzed') {
      actedRef.current.add(key)
      void triggerGraphBuild(repo_id).then(() => {
        // Graph build is async on the backend — give it a moment, then stop
        // polling and notify the parent so the canvas fetches the graph.
        setTimeout(() => {
          stopPolling()
          onReady(repo_id)
        }, 2_000)
      })
    }
  }, [repo, stopPolling, onReady])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    if (!url.trim()) return

    try {
      setLoading(true)
      actedRef.current.clear()
      const { repo_id } = await ingestRepo(url.trim())
      startPolling(repo_id)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo"
          className="flex-1 text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading || polling}
        />
        <button
          type="submit"
          disabled={loading || polling || !url.trim()}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Submitting…' : 'Ingest'}
        </button>
      </form>

      {formError && (
        <p className="text-xs text-red-600">{formError}</p>
      )}

      {repo && (
        <div className="flex items-center gap-2 text-xs">
          <span className={`px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[repo.status]}`}>
            {repo.status}
          </span>
          <span className="text-gray-500 truncate">{repo.name}</span>
          {polling && (
            <span className="text-gray-400 animate-pulse">polling…</span>
          )}
        </div>
      )}
    </div>
  )
}
