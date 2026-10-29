import { Play } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { api, type Task } from '../lib/api'
import { goToRun } from '../lib/route'
import { Button } from './ui'

const MODELS = [
  { id: 'claude-sonnet-5-5', label: 'Claude Sonnet 5.5', note: 'default' },
  { id: 'claude-opus-5-5', label: 'Claude Opus 5.5', note: 'strong' },
  { id: 'claude-haiku-5-5', label: 'Claude Haiku 5.5', note: 'cheap' },
  { id: 'random', label: 'Random baseline', note: 'no API key' },
  { id: 'oracle', label: 'Oracle script', note: 'suite tasks only' },
]

const field = 'w-full rounded-md bg-zinc-900 px-3 py-2 text-sm ring-1 ring-zinc-800 focus:ring-sky-500/60 focus:outline-none'

export function NewRun() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [taskId, setTaskId] = useState('')
  const [goal, setGoal] = useState('')
  const [url, setUrl] = useState(`${location.origin}/sites/`)
  const [model, setModel] = useState(MODELS[0].id)
  const [effort, setEffort] = useState('medium')
  const [vision, setVision] = useState(false)
  const [maxSteps, setMaxSteps] = useState(25)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.tasks().then(setTasks, () => {})
  }, [])

  const pickTask = (id: string) => {
    setTaskId(id)
    const t = tasks.find((x) => x.id === id)
    if (t) {
      setGoal(t.goal)
      setUrl(`${location.origin}${t.start}`)
    }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const { id } = await api.start({
        goal, start_url: url || null, task_id: taskId || null, model, effort, vision, max_steps: maxSteps,
      })
      goToRun(id)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const byTag = tasks.reduce<Record<string, Task[]>>((acc, t) => {
    ;(acc[t.tags[0] ?? 'other'] ??= []).push(t)
    return acc
  }, {})

  return (
    <div className="flex h-full items-start justify-center overflow-y-auto px-8 py-16">
      <form onSubmit={submit} className="w-full max-w-2xl">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">Start a run</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Watch the agent drive a real browser. Pause at any point to take over, then hand control back.
        </p>

        <div className="mt-8 space-y-5 rounded-xl bg-zinc-900/40 p-6 ring-1 ring-zinc-800">
          <div>
            <label className="mb-1.5 block text-xs font-medium tracking-wide text-zinc-400 uppercase">Task from the eval suite</label>
            <select value={taskId} onChange={(e) => pickTask(e.target.value)} className={field}>
              <option value="">Custom goal</option>
              {Object.entries(byTag).map(([tag, ts]) => (
                <optgroup key={tag} label={tag}>
                  {ts.map((t) => (
                    <option key={t.id} value={t.id}>{t.id}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium tracking-wide text-zinc-400 uppercase">Goal</label>
            <textarea
              required
              rows={3}
              value={goal}
              onChange={(e) => { setGoal(e.target.value); setTaskId('') }}
              placeholder="e.g. Add two units of the cheapest headphones to the cart."
              className={field}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium tracking-wide text-zinc-400 uppercase">Start URL</label>
            <input value={url} onChange={(e) => setUrl(e.target.value)} className={`${field} font-mono`} />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2">
              <label className="mb-1.5 block text-xs font-medium tracking-wide text-zinc-400 uppercase">Agent</label>
              <select value={model} onChange={(e) => setModel(e.target.value)} className={field}>
                {MODELS.map((m) => (
                  <option key={m.id} value={m.id}>{m.label} ({m.note})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium tracking-wide text-zinc-400 uppercase">Effort</label>
              <select value={effort} onChange={(e) => setEffort(e.target.value)} className={field} disabled={!model.startsWith('claude')}>
                {['low', 'medium', 'high'].map((x) => <option key={x}>{x}</option>)}
              </select>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-zinc-300">
              <input type="checkbox" checked={vision} onChange={(e) => setVision(e.target.checked)} className="accent-sky-500" />
              Send screenshots to the model too
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-400">
              Step budget
              <input
                type="number" min={1} max={100} value={maxSteps}
                onChange={(e) => setMaxSteps(Number(e.target.value))}
                className="w-16 rounded-md bg-zinc-900 px-2 py-1 text-sm ring-1 ring-zinc-800"
              />
            </label>
          </div>
        </div>
        {error && <p className="mt-4 rounded-md bg-rose-500/10 px-3 py-2 text-sm text-rose-300">{error}</p>}
        <div className="mt-6 flex justify-end">
          <Button type="submit" tone="primary" disabled={busy || !goal.trim()}>
            <Play className="size-4" /> {busy ? 'Starting…' : 'Start run'}
          </Button>
        </div>
      </form>
    </div>
  )
}
