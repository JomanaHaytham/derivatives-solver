// Prepares the files the static (GitHub Pages) build needs to run the Python
// math engine inside the browser. Output: frontend/static-public/
//   pyodide/            Python runtime (WebAssembly), copied from node_modules
//   engine/wheels/      SymPy + mpmath (pure-Python wheels from ./engine-wheels)
//   engine/app.json     the backend's Python source files (../backend/app)
//   engine/manifest.json
//   ...plus everything from ./public
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const out = join(root, 'static-public')
const backendApp = join(root, '..', 'backend', 'app')

rmSync(out, { recursive: true, force: true })
mkdirSync(join(out, 'pyodide'), { recursive: true })
mkdirSync(join(out, 'engine', 'wheels'), { recursive: true })

cpSync(join(root, 'public'), out, { recursive: true })

const pyodideDir = join(root, 'node_modules', 'pyodide')
for (const f of ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']) {
  cpSync(join(pyodideDir, f), join(out, 'pyodide', f))
}

const wheels = readdirSync(join(root, 'engine-wheels')).filter((f) => f.endsWith('.whl'))
if (wheels.length < 2) throw new Error('engine-wheels/ must contain the sympy and mpmath wheels')
for (const w of wheels) cpSync(join(root, 'engine-wheels', w), join(out, 'engine', 'wheels', w))

// Server-only modules are skipped: they need FastAPI / the Anthropic SDK.
const SKIP = new Set(['main.py'])
const sources = {}
function walk(dir) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) {
      if (name !== '__pycache__') walk(full)
    } else if (name.endsWith('.py') && !SKIP.has(name)) {
      sources[relative(join(backendApp, '..'), full).split('\\').join('/')] = readFileSync(full, 'utf8')
    }
  }
}
if (!existsSync(backendApp)) throw new Error(`Backend sources not found at ${backendApp}`)
walk(backendApp)
writeFileSync(join(out, 'engine', 'app.json'), JSON.stringify(sources))
writeFileSync(join(out, 'engine', 'manifest.json'), JSON.stringify({ wheels, version: Date.now() }))
console.log(`engine prepared: ${Object.keys(sources).length} Python files, wheels: ${wheels.join(', ')}`)
