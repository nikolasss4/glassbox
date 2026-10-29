import { useCallback, useEffect, useRef, useState } from 'react'
import { api, normalizeStep, wsUrl, type RunResult, type RunStatus, type Step, type Trace } from './api'

export type Frame = { data: string; width: number; height: number }

/** Loads a run's trace and, while it is live, follows it over the WebSocket. */
export function useRun(id: string | null) {
  const [trace, setTrace] = useState<Trace | null>(null)
  const [frame, setFrame] = useState<Frame | null>(null)
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const socket = useRef<WebSocket | null>(null)

  const addStep = useCallback((step: Step) => {
    setTrace((t) => (t && !t.steps.some((s) => s.index === step.index) ? { ...t, steps: [...t.steps, step] } : t))
  }, [])

  useEffect(() => {
    if (!id) return
    let cancelled = false
    setTrace(null)
    setFrame(null)
    setStatus(null)
    setError(null)

    api.trace(id).then(
      (t) => {
        if (cancelled) return
        setTrace(t)
        setStatus(t.status)
        if (t.status === 'finished') return
        const ws = new WebSocket(wsUrl(`/ws/runs/${id}`))
        socket.current = ws
        ws.onmessage = (ev) => {
          const msg = JSON.parse(ev.data)
          switch (msg.type) {
            case 'frame':
              setFrame({ data: msg.data, width: msg.width, height: msg.height })
              break
            case 'step':
              addStep(normalizeStep(id, msg.step))
              break
            case 'status':
              setStatus(msg.status)
              break
            case 'run_finished':
              setTrace((t) => (t ? { ...t, result: msg.result as RunResult, status: 'finished' } : t))
              // Reload for the final events (takeovers, eval check) written at the end.
              api.trace(id).then((full) => !cancelled && setTrace(full))
              break
            case 'error':
              setStatus('finished')
              break
          }
        }
        ws.onclose = () => {
          if (socket.current === ws) socket.current = null
        }
      },
      (e: Error) => !cancelled && setError(e.message),
    )
    return () => {
      cancelled = true
      socket.current?.close()
      socket.current = null
    }
  }, [id, addStep])

  const send = useCallback((msg: Record<string, unknown>) => {
    const ws = socket.current
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg))
  }, [])

  return { trace, frame, status, error, send, live: status === 'running' || status === 'paused' }
}
