// Thin API client — all calls go through the Vite /api proxy to localhost:8000

import type { ArchitectureGraph, ImpactResponse, RepoSummary } from './types'

const BASE = '/api'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  return res.json() as Promise<T>
}

// ── Repo ──────────────────────────────────────────────────────────────────

export async function ingestRepo(url: string): Promise<{ repo_id: string }> {
  return json(
    await fetch(`${BASE}/repo/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    }),
  )
}

export async function listRepos(): Promise<RepoSummary[]> {
  return json(await fetch(`${BASE}/repo`))
}

export async function getRepo(repoId: string): Promise<RepoSummary> {
  return json(await fetch(`${BASE}/repo/${repoId}`))
}

export async function deleteRepo(repoId: string): Promise<void> {
  await fetch(`${BASE}/repo/${repoId}`, { method: 'DELETE' })
}

// ── Analysis ──────────────────────────────────────────────────────────────

export async function triggerAnalyze(repoId: string): Promise<void> {
  await fetch(`${BASE}/repo/${repoId}/analyze`, { method: 'POST' })
}

export async function triggerGraphBuild(repoId: string): Promise<void> {
  await fetch(`${BASE}/repo/${repoId}/graph/build`, { method: 'POST' })
}

// ── Graph ─────────────────────────────────────────────────────────────────

export async function getGraph(repoId: string): Promise<ArchitectureGraph> {
  return json(await fetch(`${BASE}/repo/${repoId}/graph`))
}

// ── Impact ────────────────────────────────────────────────────────────────

export async function getImpact(repoId: string, node: string): Promise<ImpactResponse> {
  return json(await fetch(`${BASE}/repo/${repoId}/impact?node=${encodeURIComponent(node)}`))
}
