/// <reference lib="webworker" />
// Runs the Python math engine (the same code as the FastAPI backend) inside
// the browser with Pyodide. Everything is loaded from this site's own files,
// so the static build needs no server and no third-party CDN.

type InitMsg = { type: 'init'; base: string }
type ChatMsg = { type: 'chat'; id: number; payload: string }

interface PyodideLike {
  FS: { mkdirTree(path: string): void; writeFile(path: string, data: string): void }
  unpackArchive(buffer: ArrayBuffer, format: string): void
  runPython(code: string): unknown
  runPythonAsync(code: string): Promise<unknown>
  globals: { get(name: string): unknown }
}

let handle: ((payload: string) => Promise<string>) | null = null
let ready: Promise<void> | null = null

async function init(base: string) {
  const post = (stage: string) => self.postMessage({ type: 'progress', stage })
  post('Loading Python…')
  const { loadPyodide } = (await import(/* @vite-ignore */ `${base}pyodide/pyodide.mjs`)) as {
    loadPyodide: (opts: { indexURL: string }) => Promise<PyodideLike>
  }
  const py = await loadPyodide({ indexURL: `${base}pyodide/` })

  post('Loading SymPy…')
  const manifest = (await (await fetch(`${base}engine/manifest.json`)).json()) as { wheels: string[]; version: number }
  await Promise.all(
    manifest.wheels.map(async (w) => {
      const res = await fetch(`${base}engine/wheels/${w}`)
      if (!res.ok) throw new Error(`Could not download ${w}`)
      py.unpackArchive(await res.arrayBuffer(), 'wheel')
    }),
  )

  const sources = (await (await fetch(`${base}engine/app.json?v=${manifest.version}`)).json()) as Record<string, string>
  for (const [path, code] of Object.entries(sources)) {
    const full = `/engine/${path}`
    py.FS.mkdirTree(full.slice(0, full.lastIndexOf('/')))
    py.FS.writeFile(full, code)
  }

  post('Warming up the math engine…')
  py.runPython(`
import sys
sys.path.insert(0, "/engine")
from app.browser_entry import handle, warm_up
warm_up()
`)
  const pyHandle = py.globals.get('handle') as (payload: string) => Promise<string>
  handle = (payload: string) => pyHandle(payload)
}

self.onmessage = async (e: MessageEvent<InitMsg | ChatMsg>) => {
  const msg = e.data
  if (msg.type === 'init') {
    ready ??= init(msg.base)
    try {
      await ready
      self.postMessage({ type: 'ready' })
    } catch (err) {
      self.postMessage({ type: 'failed', error: String(err) })
    }
    return
  }
  if (msg.type === 'chat') {
    try {
      await ready
      const result = await handle!(msg.payload)
      self.postMessage({ type: 'result', id: msg.id, result: String(result) })
    } catch (err) {
      self.postMessage({ type: 'error', id: msg.id, error: String(err) })
    }
  }
}
