import { SimController } from './core/sim'
import { appState, type AppState } from './core/state'
import { mountCharts } from './metrics/charts'
import { FlatView } from './preview/flatView'

const app = document.querySelector<HTMLDivElement>('#app')!
const charts = document.querySelector<HTMLDivElement>('#metrics')!
const status = document.querySelector<HTMLDivElement>('#status')!

const CONNECTION_LABEL = { connecting: 'conectando…', open: 'conectado', reconnecting: 'reconectando…' }
const HELP = 's: iniciar · espacio: pausa · r: reiniciar · n: escena nueva · e: CSV · 1/2/3: velocidad'

function renderStatus(s: AppState) {
  const parts = [CONNECTION_LABEL[s.connection], `${s.simState} ×${s.speed}`]
  if (s.error) parts.push(`⚠ ${s.error}`)
  status.textContent = `${parts.join(' · ')}   —   ${HELP}`
}

async function main() {
  const sim = new SimController()
  let view: FlatView | null = null
  mountCharts(charts)

  appState.subscribe((s, prev) => {
    if (s.scene && s.scene.id !== prev.scene?.id) {
      view?.dispose()
      view = new FlatView(app, s.scene.nx, s.scene.ny, s.scene.cell_size)
    }
    if (view && s.frame && s.frame !== prev.frame) view.update(s.frame)
    if (s.error && s.error !== prev.error) console.error(s.error)
    // Dev: ignite at the center of every new session.
    if (s.scene && s.sessionId && s.sessionId !== prev.sessionId) {
      sim.ignite((s.scene.nx * s.scene.cell_size) / 2, (s.scene.ny * s.scene.cell_size) / 2)
    }
    renderStatus(s)
  })
  renderStatus(appState.get())

  // Dev shortcuts until the control panel exists.
  window.addEventListener('keydown', (e) => {
    const { simState, sceneRequest } = appState.get()
    if (e.key === 's' || (e.code === 'Space' && simState === 'idle')) sim.start()
    else if (e.code === 'Space') simState === 'running' ? sim.pause() : sim.resume()
    else if (e.key === 'r') sim.reset()
    else if (e.key === 'e') sim.exportCsv()
    else if (e.key === 'n' && sceneRequest) sim.loadScene({ ...sceneRequest, seed: sceneRequest.seed + 1 })
    else if (e.key === '1') sim.setSpeed(1)
    else if (e.key === '2') sim.setSpeed(5)
    else if (e.key === '3') sim.setSpeed(20)
  })

  await sim.init()
  await sim.loadScene({ preset: 'flat', density: 1, seed: 0 })
  await sim.start()
}

main().catch((e) => {
  app.textContent = `Error: ${e.message}`
  console.error(e)
})
