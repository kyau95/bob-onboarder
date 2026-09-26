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
  const [error, setError]     = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const { repo, polling, startPolling } = useRepoPolling()

  // Track which pipeline steps have already been triggered (per repo_id)
  const pipelineRef = useRef<{ id: string; step: 'analyze' | 'build' | 'done' } | null>(null)

  // Drive the analyze → graph/build pipeline as status advances
  useEffect(() => {
    if (!repo) return

    const { repo_id, status } = repo
    const p = pipelineRef.current

    if (status === 'ready' && (p === null || (p.id === repo_id && p.step === 'analyze'))) {
      pipelineRef.current = { id: repo_id, step: 'build' }
      void triggerAnalyze(repo_id).then(() => startPolling(repo_id))
    } else if (status === 'analyzed' && p?.id === repo_id && p.step === 'build') {
      pipelineRef.current = { id: repo_id, step: 'done' }
      void triggerGraphBuild(repo_id).then(() => {
        setTimeout(() => onReady(repo_id), 1_500)
      })
    }
  }, [repo, startPolling, onReady])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!url.trim()) return

    try {
      setLoading(true)
      pipelineRef.current = null
      const { repo_id } = await ingestRepo(url.trim())
      pipelineRef.current = { id: repo_id, step: 'analyze' }
      startPolling(repo_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
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

      {error && (
        <p className="text-xs text-red-600">{error}</p>
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
