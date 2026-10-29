import { Globe } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Frame } from '../lib/useRun'

/** Browser-chrome frame around either the live screencast or a recorded screenshot. */
export function Viewport({
  frame, imageUrl, url, badge, children,
}: {
  frame: Frame | null
  imageUrl?: string
  url?: string
  badge?: ReactNode
  children?: ReactNode
}) {
  const src = frame ? `data:image/jpeg;base64,${frame.data}` : imageUrl
  return (
    <div className="overflow-hidden rounded-xl bg-zinc-900 ring-1 ring-zinc-800 shadow-2xl shadow-black/40">
      <div className="flex items-center gap-3 border-b border-zinc-800 px-3 py-2">
        <div className="flex gap-1.5">
          <span className="size-2.5 rounded-full bg-zinc-700" />
          <span className="size-2.5 rounded-full bg-zinc-700" />
          <span className="size-2.5 rounded-full bg-zinc-700" />
        </div>
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md bg-zinc-950/70 px-2.5 py-1 font-mono text-xs text-zinc-400">
          <Globe className="size-3.5 shrink-0 text-zinc-600" />
          <span className="truncate">{url ?? ''}</span>
        </div>
        {badge}
      </div>
      <div className="relative aspect-[16/10] bg-zinc-950">
        {src ? (
          <img src={src} alt="Browser view" draggable={false} className="absolute inset-0 h-full w-full object-contain select-none" />
        ) : (
          <div className="absolute inset-0 grid place-items-center text-sm text-zinc-600">Waiting for the first frame…</div>
        )}
        {children}
      </div>
    </div>
  )
}
