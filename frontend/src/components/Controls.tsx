import { Hand, Play, Square } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import type { RunStatus } from '../lib/api'
import { Button } from './ui'

type Send = (msg: Record<string, unknown>) => void

export function Controls({ status, send }: { status: RunStatus | null; send: Send }) {
  if (status === 'running')
    return (
      <div className="flex gap-2">
        <Button tone="warn" onClick={() => send({ type: 'pause' })} title="Pause the agent and control the browser yourself">
          <Hand className="size-4" /> Take over
        </Button>
        <Button tone="danger" onClick={() => send({ type: 'cancel' })} title="Stop the run">
          <Square className="size-3.5" /> Stop
        </Button>
      </div>
    )
  return null
}

/** Shown under the viewport while the human is in control. */
export function ResumeBar({ send }: { send: Send }) {
  const [note, setNote] = useState('')
  const resume = (e: FormEvent) => {
    e.preventDefault()
    send({ type: 'resume', note })
  }
  return (
    <form onSubmit={resume} className="mt-4 flex items-center gap-3 rounded-xl bg-amber-400/[0.07] p-3 ring-1 ring-amber-400/30">
      <Hand className="ml-1 size-5 shrink-0 text-amber-300" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-amber-100">You're in control. Click and type directly in the page.</p>
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Optional note for the agent, e.g. “I accepted the cookie banner”"
          className="mt-1.5 w-full rounded-md bg-zinc-950/60 px-2.5 py-1.5 text-sm ring-1 ring-amber-400/20 placeholder:text-zinc-500 focus:ring-amber-400/60 focus:outline-none"
        />
      </div>
      <Button type="submit" tone="primary">
        <Play className="size-4" /> Resume agent
      </Button>
      <Button tone="danger" onClick={() => send({ type: 'cancel' })}>
        <Square className="size-3.5" /> Stop
      </Button>
    </form>
  )
}
