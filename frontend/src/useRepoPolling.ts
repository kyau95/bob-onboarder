// Hook: poll a repo's status until it reaches a terminal state or errors.

import { useCallback, useEffect, useRef, useState } from 'react'
import { getRepo } from './api'
import type { RepoStatus, RepoSummary } from './types'

const TERMINAL: RepoStatus[] = ['ready', 'analyzed', 'error']
const POLL_MS = 2_000

interface UseRepoPollingResult {
  repo: RepoSummary | null
  polling: boolean
  startPolling: (repoId: string) => void
  stopPolling: () => void
}

export function useRepoPolling(): UseRepoPollingResult {
  const [repo, setRepo] = useState<RepoSummary | null>(null)
  const [polling, setPolling] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const repoIdRef = useRef<string | null>(null)

  const stopPolling = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setPolling(false)
  }, [])

  const tick = useCallback(async () => {
    const id = repoIdRef.current
    if (!id) return
    try {
      const data = await getRepo(id)
      setRepo(data)
      if (TERMINAL.includes(data.status)) {
        stopPolling()
      } else {
        timerRef.current = setTimeout(tick, POLL_MS)
      }
    } catch {
      stopPolling()
    }
  }, [stopPolling])

  const startPolling = useCallback(
    (repoId: string) => {
      repoIdRef.current = repoId
      setPolling(true)
      timerRef.current = setTimeout(tick, POLL_MS)
    },
    [tick],
  )

  useEffect(() => () => stopPolling(), [stopPolling])

  return { repo, polling, startPolling, stopPolling }
}
