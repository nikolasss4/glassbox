// Types mirror the backend's trace format (src/glassbox/trace.py, agent.py).

export type Usage = {
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
}

export type Action = { name: string; args: Record<string, unknown>; reason: string }

export type Step = {
  index: number
  url: string
  feedback: string | null
  thought: string
  thinking: string
  action: Action
  result: { ok: boolean; message: string }
  usage: Usage
  model: string
  latency_s: number
  action_s: number
  cost_usd: number
  human_note: string | null
  screenshot_url?: string
  observation?: string
  t?: number
}

export type RunResult = {
  stop_reason: 'done' | 'max_steps' | 'timeout' | 'error' | 'cancelled'
  success_claimed: boolean
  answer: string
  steps: number
  usage: Usage
  cost_usd: number
  duration_s: number
  error: string | null
}

export type TraceEvent = { t: number; kind: string; note?: string; success?: boolean; error?: string | null }

export type RunStatus = 'running' | 'paused' | 'finished'

export type RunSummary = {
  id: string
  created_at: string
  status: RunStatus
  goal: string
  start_url: string | null
  task_id: string | null
  provider: string
  result: RunResult | null
  n_steps: number
  eval?: { trial: number }
}

export type Trace = Omit<RunSummary, 'n_steps'> & { steps: Step[]; events: TraceEvent[] }

export type Task = { id: string; goal: string; start: string; tags: string[] }

export type NewRun = {
  goal: string
  start_url: string | null
  task_id: string | null
  model: string
  effort: string
  vision: boolean
  max_steps: number
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

/** Trace files store screenshot names and raw model output; make them UI-ready. */
export function normalizeStep(runId: string, s: Record<string, unknown>): Step {
  const raw = (s.raw ?? {}) as { thinking?: string }
  const shot = s.screenshot as string | undefined
  return {
    ...(s as unknown as Step),
    thinking: (s.thinking as string | undefined) ?? raw.thinking ?? '',
    screenshot_url: (s.screenshot_url as string | undefined) ?? (shot ? `/api/runs/${runId}/assets/${shot}` : undefined),
  }
}

export const api = {
  runs: () => fetch('/api/runs').then((r) => json<RunSummary[]>(r)),
  tasks: () => fetch('/api/tasks').then((r) => json<Task[]>(r)),
  trace: async (id: string) => {
    const t = await fetch(`/api/runs/${id}`).then((r) => json<Trace>(r))
    return { ...t, steps: t.steps.map((s) => normalizeStep(id, s as unknown as Record<string, unknown>)) }
  },
  start: (body: NewRun) =>
    fetch('/api/runs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => json<{ id: string }>(r)),
}

export function wsUrl(path: string): string {
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${path}`
}
