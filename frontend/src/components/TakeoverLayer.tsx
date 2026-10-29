import { useEffect, useRef } from 'react'
import type { Frame } from '../lib/useRun'

type Send = (msg: Record<string, unknown>) => void

// CDP modifier bits.
const modifiers = (e: { altKey: boolean; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }) =>
  (e.altKey ? 1 : 0) | (e.ctrlKey ? 2 : 0) | (e.metaKey ? 4 : 0) | (e.shiftKey ? 8 : 0)

const BUTTONS = ['left', 'middle', 'right'] as const

/**
 * Transparent layer over the live view. While the human is in control it turns mouse,
 * wheel and keyboard events into CDP Input.dispatch* calls on the agent's page.
 */
export function TakeoverLayer({ frame, send }: { frame: Frame | null; send: Send }) {
  const el = useRef<HTMLDivElement>(null)
  const lastMove = useRef(0)

  const point = (e: { clientX: number; clientY: number }) => {
    const r = el.current!.getBoundingClientRect()
    const w = frame?.width ?? 1280
    const h = frame?.height ?? 800
    return { x: ((e.clientX - r.left) / r.width) * w, y: ((e.clientY - r.top) / r.height) * h }
  }
  const mouse = (event: string, e: React.MouseEvent | WheelEvent, extra: Record<string, unknown> = {}) =>
    send({ type: 'input', kind: 'mouse', event, ...point(e), modifiers: modifiers(e), ...extra })

  useEffect(() => {
    const node = el.current!
    node.focus()
    // Wheel needs a non-passive listener so the outer page doesn't scroll as well.
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      mouse('mouseWheel', e, { deltaX: e.deltaX, deltaY: e.deltaY })
    }
    node.addEventListener('wheel', onWheel, { passive: false })
    return () => node.removeEventListener('wheel', onWheel)
  })

  const key = (event: 'keyDown' | 'keyUp') => (e: React.KeyboardEvent) => {
    e.preventDefault()
    send({ type: 'input', kind: 'key', event, key: e.key, code: e.code, modifiers: modifiers(e) })
  }

  return (
    <div
      ref={el}
      tabIndex={0}
      aria-label="Remote browser: you are in control"
      className="absolute inset-0 cursor-crosshair outline-none"
      onMouseDown={(e) => {
        el.current?.focus()
        mouse('mousePressed', e, { button: BUTTONS[e.button] ?? 'left', clickCount: e.detail || 1 })
      }}
      onMouseUp={(e) => mouse('mouseReleased', e, { button: BUTTONS[e.button] ?? 'left', clickCount: e.detail || 1 })}
      onMouseMove={(e) => {
        const now = performance.now()
        if (now - lastMove.current < 40) return
        lastMove.current = now
        mouse('mouseMoved', e)
      }}
      onContextMenu={(e) => e.preventDefault()}
      onKeyDown={key('keyDown')}
      onKeyUp={key('keyUp')}
    />
  )
}
