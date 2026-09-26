// Sidebar — repo list with status badges + per-repo selection

import { useEffect, useState } from 'react'
import { deleteRepo, listRepos, triggerAnalyze, triggerGraphBuild } from '../api'
import type { RepoStatus, RepoSummary } from '../types'

const STATUS_DOT: Record<RepoStatus, string> = {
  pending:   'bg-gray-400',
  cloning:   'bg-yellow-400 animate-pulse',
  ready:     'bg-blue-400',
  analyzing: 'bg-yellow-400 animate-pulse',
  analyzed:  'bg-green-500',
  error:     'bg-red-500',
}

interface Props {
  selectedId: string | null
  onSelect: (repoId: string) => void
}

export function Sidebar({ selectedId, onSelect }: Props) {
  const [repos, setRepos]     = useState<RepoSummary[]>([])
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const data = await listRepos()
      setRepos(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function handleAnalyze(repoId: string, e: React.MouseEvent) {
    e.stopPropagation()
    await triggerAnalyze(repoId)
    await triggerGraphBuild(repoId)
    setTimeout(load, 1_000)
  }

  async function handleDelete(repoId: string, e: React.MouseEvent) {
    e.stopPropagation()
    await deleteRepo(repoId)
    await load()
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Repositories
        </span>
        <button
          onClick={load}
          disabled={loading}
          className="text-xs text-blue-500 hover:underline disabled:opacity-50"
        >
          {loading ? '…' : 'Refresh'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
        {repos.length === 0 && !loading && (
          <p className="p-4 text-xs text-gray-400">No repositories yet. Ingest one above.</p>
        )}
        {repos.map(repo => (
          <button
            key={repo.repo_id}
            onClick={() => onSelect(repo.repo_id)}
            className={`w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-gray-50 transition-colors ${
              selectedId === repo.repo_id ? 'bg-blue-50 border-l-2 border-blue-500' : ''
            }`}
          >
            {/* Status dot */}
            <span
              className={`mt-1 shrink-0 w-2 h-2 rounded-full ${STATUS_DOT[repo.status]}`}
            />

            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate">{repo.name}</p>
              <p className="text-xs text-gray-400 truncate">{repo.url}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-gray-500">{repo.status}</span>

                {repo.status === 'ready' && (
                  <button
                    onClick={e => handleAnalyze(repo.repo_id, e)}
                    className="text-xs text-indigo-600 hover:underline"
                  >
                    Analyze →
                  </button>
                )}
              </div>
            </div>

            {/* Delete */}
            <button
              onClick={e => handleDelete(repo.repo_id, e)}
              className="text-gray-300 hover:text-red-500 text-base shrink-0"
              title="Delete repo"
            >
              ×
            </button>
          </button>
        ))}
      </div>
    </div>
  )
}
