// GraphCanvas — React Flow canvas with typed custom nodes + edge evidence drawer

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  type EdgeMouseHandler,
  type Node,
  type Edge,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { getGraph } from '../api'
import type { ArchitectureGraph, Evidence, GEdge, NodeType, RFNodeData } from '../types'

// ── Colour palette by node type ─────────────────────────────────────────────

const NODE_COLORS: Record<NodeType, { bg: string; border: string; text: string }> = {
  service:      { bg: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
  component:    { bg: '#e0e7ff', border: '#6366f1', text: '#3730a3' },
  module:       { bg: '#f1f5f9', border: '#94a3b8', text: '#334155' },
  class:        { bg: '#fef3c7', border: '#f59e0b', text: '#92400e' },
  function:     { bg: '#ecfdf5', border: '#10b981', text: '#065f46' },
  api_endpoint: { bg: '#fce7f3', border: '#ec4899', text: '#9d174d' },
  database:     { bg: '#fef9c3', border: '#ca8a04', text: '#713f12' },
  queue:        { bg: '#ffe4e6', border: '#f43f5e', text: '#9f1239' },
  cache:        { bg: '#f0fdf4', border: '#22c55e', text: '#14532d' },
  external:     { bg: '#f5f3ff', border: '#8b5cf6', text: '#4c1d95' },
  dependency:   { bg: '#f8fafc', border: '#cbd5e1', text: '#475569' },
  unknown:      { bg: '#fafafa', border: '#d1d5db', text: '#6b7280' },
}

// ── Custom node component ────────────────────────────────────────────────────

function ArchNode({ data }: { data: RFNodeData }) {
  const type = (data.nodeType ?? 'unknown') as NodeType
  const colors = NODE_COLORS[type] ?? NODE_COLORS.unknown
  const opacity = data.dimmed ? 0.25 : 1

  return (
    <div
      style={{
        background: colors.bg,
        border: `2px solid ${data.highlighted ? '#f97316' : colors.border}`,
        borderRadius: 6,
        padding: '4px 10px',
        minWidth: 120,
        maxWidth: 200,
        opacity,
        boxShadow: data.highlighted ? '0 0 0 3px rgba(249,115,22,0.35)' : undefined,
        transition: 'opacity 0.2s, box-shadow 0.2s',
      }}
    >
      <div
        style={{
          fontSize: 9,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: colors.border,
          marginBottom: 2,
        }}
      >
        {type.replace('_', ' ')}
      </div>
      <div
        style={{
          fontSize: 12,
          fontWeight: 700,
          color: colors.text,
          wordBreak: 'break-all',
        }}
      >
        {String(data.label)}
      </div>
      {data.file && (
        <div
          style={{
            fontSize: 9,
            color: '#94a3b8',
            marginTop: 2,
            wordBreak: 'break-all',
          }}
        >
          {String(data.file).split('/').pop()}
        </div>
      )}
    </div>
  )
}

const nodeTypes: NodeTypes = {
  service:     ArchNode as never,
  component:   ArchNode as never,
  module:      ArchNode as never,
  class:       ArchNode as never,
  function:    ArchNode as never,
  apiEndpoint: ArchNode as never,
  database:    ArchNode as never,
  queue:       ArchNode as never,
  cache:       ArchNode as never,
  external:    ArchNode as never,
  dependency:  ArchNode as never,
  default:     ArchNode as never,
}

// ── Evidence drawer ──────────────────────────────────────────────────────────

interface EvidenceDrawerProps {
  edge: GEdge | null
  onClose: () => void
}

function EvidenceDrawer({ edge, onClose }: EvidenceDrawerProps) {
  if (!edge) return null
  return (
    <div className="absolute right-0 top-0 h-full w-80 bg-white border-l border-gray-200 shadow-lg z-10 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-indigo-600">
            {edge.type}
          </span>
          <p className="text-xs text-gray-500 mt-0.5">
            confidence {(edge.confidence * 100).toFixed(0)}%
          </p>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">
          ×
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {edge.evidence.length === 0 ? (
          <p className="text-xs text-gray-400">No evidence recorded for this edge.</p>
        ) : (
          edge.evidence.map((ev: Evidence, i: number) => (
            <div key={i} className="rounded border border-gray-100 p-3 bg-gray-50">
              <p className="text-xs font-mono text-blue-700 break-all">
                {ev.file}{ev.line != null ? `:${ev.line}` : ''}
              </p>
              {ev.snippet && (
                <pre className="mt-1 text-xs text-gray-600 whitespace-pre-wrap break-all">
                  {ev.snippet}
                </pre>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ── GraphCanvas ──────────────────────────────────────────────────────────────

interface Props {
  repoId: string
  highlightedNodeIds?: Set<string>
}

function archToFlow(
  arch: ArchitectureGraph,
  highlightedNodeIds: Set<string>,
): { nodes: Node[]; edges: Edge[]; edgeMap: Map<string, GEdge> } {
  const hasHighlight = highlightedNodeIds.size > 0
  const edgeMap = new Map<string, GEdge>()

  const nodes: Node[] = arch.nodes.map(n => ({
    id: n.id,
    type: _rfType(n.type),
    position: { x: 0, y: 0 }, // positions come from backend spring layout via react-flow-layout below
    data: {
      label: n.label,
      nodeType: n.type,
      file: n.file,
      language: n.language,
      highlighted: highlightedNodeIds.has(n.id),
      dimmed: hasHighlight && !highlightedNodeIds.has(n.id),
    } satisfies RFNodeData,
  }))

  const edges: Edge[] = arch.edges.map(e => {
    edgeMap.set(e.id, e)
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.type,
      animated: e.type === 'HTTP_CALL' || e.type === 'CALLS',
      style: { stroke: _edgeColor(e.type), strokeWidth: 1.5 },
      labelStyle: { fontSize: 9, fill: '#64748b' },
      data: { edgeType: e.type, confidence: e.confidence, evidence: e.evidence },
    }
  })

  return { nodes, edges, edgeMap }
}

function _rfType(t: NodeType): string {
  const map: Record<NodeType, string> = {
    service: 'service', component: 'component', module: 'module',
    class: 'class', function: 'function', api_endpoint: 'apiEndpoint',
    database: 'database', queue: 'queue', cache: 'cache',
    external: 'external', dependency: 'dependency', unknown: 'default',
  }
  return map[t] ?? 'default'
}

function _edgeColor(type: string): string {
  switch (type) {
    case 'IMPORTS':      return '#94a3b8'
    case 'HTTP_CALL':    return '#3b82f6'
    case 'DB_QUERY':     return '#f59e0b'
    case 'CALLS':        return '#10b981'
    case 'CO_CHANGE':    return '#a78bfa'
    case 'DEPENDS_ON':   return '#cbd5e1'
    case 'EXPOSES':      return '#ec4899'
    default:             return '#d1d5db'
  }
}

// Auto-layout: simple left→right dagre-style grid since dagre isn't installed.
// Bucket nodes by type tier, then space them out.
const TYPE_TIER: Record<string, number> = {
  service: 0, component: 1, module: 2,
  class: 3, function: 3, apiEndpoint: 3,
  database: 4, queue: 4, cache: 4,
  external: 5, dependency: 5, default: 6,
}

function layoutNodes(nodes: Node[]): Node[] {
  const tiers: Record<number, Node[]> = {}
  for (const n of nodes) {
    const tier = TYPE_TIER[n.type ?? 'default'] ?? 6
    ;(tiers[tier] ??= []).push(n)
  }
  return nodes.map(n => {
    const tier = TYPE_TIER[n.type ?? 'default'] ?? 6
    const tierNodes = tiers[tier] ?? []
    const idx = tierNodes.indexOf(n)
    return {
      ...n,
      position: {
        x: tier * 260,
        y: idx * 90,
      },
    }
  })
}

export function GraphCanvas({ repoId, highlightedNodeIds = new Set() }: Props) {
  const [arch, setArch] = useState<ArchitectureGraph | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<GEdge | null>(null)

  useEffect(() => {
    if (!repoId) return
    setLoading(true)
    setError(null)
    getGraph(repoId)
      .then(setArch)
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load graph'))
      .finally(() => setLoading(false))
  }, [repoId])

  const { nodes, edges, edgeMap } = useMemo(() => {
    if (!arch) return { nodes: [], edges: [], edgeMap: new Map<string, GEdge>() }
    const result = archToFlow(arch, highlightedNodeIds)
    result.nodes = layoutNodes(result.nodes)
    return result
  }, [arch, highlightedNodeIds])

  const onEdgeClick: EdgeMouseHandler = useCallback(
    (_evt, edge) => {
      const g = edgeMap.get(edge.id)
      setSelectedEdge(g ?? null)
    },
    [edgeMap],
  )

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
        Loading graph…
      </div>
    )
  }
  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-red-500 px-8 text-center">
        {error}
      </div>
    )
  }
  if (!arch) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
        Select a repository to view its architecture graph.
      </div>
    )
  }

  return (
    <div className="relative flex-1 flex flex-col min-h-0">
      {/* Stats bar */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-gray-100 bg-white text-xs text-gray-500">
        <span><strong className="text-gray-700">{arch.node_count}</strong> nodes</span>
        <span><strong className="text-gray-700">{arch.edge_count}</strong> edges</span>
        {arch.built_at && (
          <span className="text-gray-400">built {new Date(arch.built_at).toLocaleString()}</span>
        )}
        <span className="ml-auto text-gray-400">Click an edge to inspect evidence</span>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative min-h-0">
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onEdgeClick={onEdgeClick}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.1}
            deleteKeyCode={null}
          >
            <Background gap={20} color="#f1f5f9" />
            <Controls />
            <MiniMap
              nodeColor={n => {
                const nt = (n.data as RFNodeData).nodeType as NodeType
                return NODE_COLORS[nt]?.border ?? '#94a3b8'
              }}
              zoomable
              pannable
            />
          </ReactFlow>
        </ReactFlowProvider>

        {/* Evidence drawer overlaid on right side */}
        <EvidenceDrawer edge={selectedEdge} onClose={() => setSelectedEdge(null)} />
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 px-4 py-2 border-t border-gray-100 bg-white">
        {(Object.entries(NODE_COLORS) as [NodeType, { bg: string; border: string; text: string }][])
          .filter(([t]) => t !== 'unknown')
          .map(([type, c]) => (
            <div key={type} className="flex items-center gap-1">
              <div
                className="w-3 h-3 rounded-sm border"
                style={{ background: c.bg, borderColor: c.border }}
              />
              <span className="text-xs text-gray-500">{type.replace('_', ' ')}</span>
            </div>
          ))}
      </div>
    </div>
  )
}
