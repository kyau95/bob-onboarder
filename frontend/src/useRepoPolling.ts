// Hook: poll a repo's status on a fixed interval.
// Stops only on 'error' or when stopPolling() is called explicitly.

import { useCallback, useEffect, useRef, useState } from 'react'
import { getRepo } from './api'
import type { RepoSummary } from './types'

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
    timerRef.current = null
    setPolling(false)
  }, [])

  const tick = useCallback(async () => {
    const id = repoIdRef.current
    if (!id) return
    try {
      const data = await getRepo(id)
      setRepo(data)
      if (data.status === 'error') {
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
      // Clear any existing timer before starting a new one
      if (timerRef.current) clearTimeout(timerRef.current)
      repoIdRef.current = repoId
      setPolling(true)
      timerRef.current = setTimeout(tick, POLL_MS)
    },
    [tick],
  )

  useEffect(() => () => stopPolling(), [stopPolling])

  return { repo, polling, startPolling, stopPolling }
}
