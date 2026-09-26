// Shared types mirroring backend Pydantic models

export type RepoStatus =
  | 'pending'
  | 'cloning'
  | 'ready'
  | 'analyzing'
  | 'analyzed'
  | 'error'

export interface RepoSummary {
  repo_id: string
  name: string
  url: string
  branch: string
  status: RepoStatus
  description: string | null
  created_at: string
  updated_at: string
}

export type NodeType =
  | 'service'
  | 'component'
  | 'module'
  | 'class'
  | 'function'
  | 'api_endpoint'
  | 'database'
  | 'queue'
  | 'cache'
  | 'external'
  | 'dependency'
  | 'unknown'

export type EdgeType =
  | 'IMPORTS'
  | 'CALLS'
  | 'HTTP_CALL'
  | 'DB_QUERY'
  | 'PUBLISHES_TO'
  | 'SUBSCRIBES_TO'
  | 'DEPENDS_ON'
  | 'CO_CHANGE'
  | 'CONTAINS'
  | 'EXPOSES'

export interface Evidence {
  file: string
  line: number | null
  snippet: string
}

export interface GNode {
  id: string
  type: NodeType
  label: string
  file: string | null
  language: string | null
  metadata: Record<string, unknown>
}

export interface GEdge {
  id: string
  source: string
  target: string
  type: EdgeType
  evidence: Evidence[]
  confidence: number
}

export interface ArchitectureGraph {
  repo_id: string
  nodes: GNode[]
  edges: GEdge[]
  built_at: string
  node_count: number
  edge_count: number
}

// React Flow data shapes
export interface RFNodeData {
  label: string
  nodeType: NodeType
  file: string | null
  language: string | null
  highlighted?: boolean
  dimmed?: boolean
  [key: string]: unknown
}

export interface RFEdgeData {
  edgeType: EdgeType
  confidence: number
  evidence: Evidence[]
}

// Impact analysis
export interface AffectedNode {
  node: GNode
  distance: number
  max_confidence: number
  is_test: boolean
}

export interface ImpactResponse {
  repo_id: string
  target_node_id: string
  target_node: GNode | null
  direct: AffectedNode[]
  transitive: AffectedNode[]
  tests_to_run: string[]
  total_affected: number
}
