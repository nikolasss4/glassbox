import { useEffect, useState } from 'react'

/** Minimal hash router: `#/` for a new run, `#/run/<id>` for a run. */
export function useRoute(): { runId: string | null } {
  const parse = () => {
    const m = location.hash.match(/^#\/run\/([\w-]+)/)
    return { runId: m ? m[1] : null }
  }
  const [route, setRoute] = useState(parse)
  useEffect(() => {
    const on = () => setRoute(parse())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

export const goToRun = (id: string) => (location.hash = `#/run/${id}`)
export const goHome = () => (location.hash = '#/')
