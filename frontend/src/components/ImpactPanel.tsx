// ImpactPanel — enter a node name, run /impact, highlight affected nodes

import { useState } from 'react'
import { getImpact } from '../api'
import type { AffectedNode, ImpactResponse } from '../types'

interface Props {
  repoId: string
  onHighlight: (nodeIds: Set<string>) => void
}

export function ImpactPanel({ repoId, onHighlight }: Props) {
  const [query, setQuery]       = useState('')
  const [result, setResult]     = useState<ImpactResponse | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

  async function run(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setError(null)
    setLoading(true)
    try {
      const data = await getImpact(repoId, query.trim())
      setResult(data)
      // Highlight target + all affected nodes
      const ids = new Set<string>([
        ...(data.target_node ? [data.target_node.id] : []),
        ...data.direct.map((a: AffectedNode) => a.node.id),
        ...data.transitive.map((a: AffectedNode) => a.node.id),
      ])
      onHighlight(ids)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setResult(null)
      onHighlight(new Set())
    } finally {
      setLoading(false)
    }
  }

  function clear() {
    setQuery('')
    setResult(null)
    setError(null)
    onHighlight(new Set())
  }

  return (
    <div className="flex flex-col gap-3 text-sm">
      <h3 className="font-semibold text-gray-700 text-xs uppercase tracking-wide">
        Impact Analysis
      </h3>

      <form onSubmit={run} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="node name or label…"
          className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-orange-400"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-2 py-1.5 bg-orange-500 text-white text-xs rounded hover:bg-orange-600 disabled:opacity-50"
        >
          {loading ? '…' : 'Run'}
        </button>
        {result && (
          <button
            type="button"
            onClick={clear}
            className="px-2 py-1.5 text-xs text-gray-500 border border-gray-300 rounded hover:bg-gray-50"
          >
            Clear
          </button>
        )}
      </form>

      {error && <p className="text-xs text-red-500">{error}</p>}

      {result && (
        <div className="space-y-2">
          {/* Target */}
          {result.target_node && (
            <div className="rounded bg-orange-50 border border-orange-200 px-3 py-2">
              <p className="text-xs font-semibold text-orange-700">Target</p>
              <p className="text-xs text-orange-900 truncate">{result.target_node.label}</p>
            </div>
          )}

          {/* Counts */}
          <div className="flex gap-3">
            <Chip label="Direct" count={result.direct.length} color="red" />
            <Chip label="Transitive" count={result.transitive.length} color="amber" />
            <Chip label="Tests" count={result.tests_to_run.length} color="green" />
          </div>

          {/* Direct */}
          {result.direct.length > 0 && (
            <NodeList title="Directly affected" nodes={result.direct} />
          )}

          {/* Transitive (collapsed if long) */}
          {result.transitive.length > 0 && (
            <NodeList
              title={`Transitive (${result.transitive.length})`}
              nodes={result.transitive.slice(0, 10)}
              truncated={result.transitive.length > 10}
            />
          )}

          {/* Tests */}
          {result.tests_to_run.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-600 mb-1">Tests to run</p>
              <ul className="space-y-0.5">
                {result.tests_to_run.map(f => (
                  <li key={f} className="text-xs font-mono text-green-700 truncate">{f}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Chip({ label, count, color }: { label: string; count: number; color: 'red' | 'amber' | 'green' }) {
  const styles = {
    red:   'bg-red-50 text-red-700 border-red-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    green: 'bg-green-50 text-green-700 border-green-200',
  }
  return (
    <div className={`rounded border px-2 py-1 text-center ${styles[color]}`}>
      <p className="text-sm font-bold leading-none">{count}</p>
      <p className="text-xs">{label}</p>
    </div>
  )
}

function NodeList({
  title, nodes, truncated = false,
}: {
  title: string
  nodes: AffectedNode[]
  truncated?: boolean
}) {
  return (
    <div>
      <p className="text-xs font-medium text-gray-600 mb-1">{title}</p>
      <ul className="space-y-0.5">
        {nodes.map(a => (
          <li key={a.node.id} className="text-xs flex items-center gap-1.5">
            <span className="shrink-0 w-5 text-center text-gray-400 font-mono">d{a.distance}</span>
            <span className="truncate text-gray-700">{a.node.label}</span>
            {a.is_test && (
              <span className="shrink-0 text-green-600">✓test</span>
            )}
          </li>
        ))}
        {truncated && (
          <li className="text-xs text-gray-400 italic">… more</li>
        )}
      </ul>
    </div>
  )
}
