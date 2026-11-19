import { SimController } from './core/sim'
import { appState, type AppState } from './core/state'
import { mountCharts } from './metrics/charts'
import { mountScene } from './scene'
import { mountPanel } from './ui'

const app = document.querySelector<HTMLDivElement>('#app')!
const panel = document.querySelector<HTMLDivElement>('#panel')!
const charts = document.querySelector<HTMLDivElement>('#metrics')!
const status = document.querySelector<HTMLDivElement>('#status')!

const CONNECTION_LABEL = { connecting: 'conectando…', open: 'conectado', reconnecting: 'reconectando…' }

function renderStatus(s: AppState) {
  const parts = [CONNECTION_LABEL[s.connection], `t = ${(s.frame?.t ?? 0).toFixed(0)} s`]
  if (s.error) parts.push(`⚠ ${s.error}`)
  status.textContent = parts.join(' · ')
}

async function main() {
  const sim = new SimController()
  mountCharts(charts)
  mountScene(app, sim)

  appState.subscribe((s, prev) => {
    if (s.error && s.error !== prev.error) console.error(s.error)
    if (s.connection !== prev.connection || s.error !== prev.error || s.frame !== prev.frame) renderStatus(s)
  })
  renderStatus(appState.get())

  await sim.init()
  mountPanel(panel, sim)
  await sim.loadScene({ preset: 'flat', density: 1, seed: 0 })
}

main().catch((e) => {
  app.textContent = `Error: ${e.message}`
  console.error(e)
})
