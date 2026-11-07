import { buildScene } from './core/api'
import { SimController } from './core/sim'
import { appState } from './core/state'
import { mountCharts } from './metrics/charts'
import { FlatView } from './preview/flatView'

const app = document.querySelector<HTMLDivElement>('#app')!
const charts = document.querySelector<HTMLDivElement>('#metrics')!
const status = document.querySelector<HTMLDivElement>('#status')!

async function main() {
  const meta = await buildScene('flat')
  appState.set({ scene: meta })
  const view = new FlatView(app, meta.nx, meta.ny, meta.cell_size)
  mountCharts(charts)

  appState.subscribe((s, prev) => {
    if (s.frame && s.frame !== prev.frame) view.update(s.frame)
    if (s.error && s.error !== prev.error) console.error(s.error)
    status.textContent = `${s.simState} ×${s.speed}  ·  espacio: pausa · r: reiniciar · 1/2/3: velocidad`
  })

  const sim = new SimController()
  const igniteCenter = () => sim.ignite((meta.nx * meta.cell_size) / 2, (meta.ny * meta.cell_size) / 2)

  // Dev shortcuts until the control panel exists.
  window.addEventListener('keydown', (e) => {
    const { simState } = appState.get()
    if (e.code === 'Space') simState === 'running' ? sim.pause() : sim.resume()
    else if (e.key === 'r') sim.reset()
    else if (e.key === '1') sim.setSpeed(1)
    else if (e.key === '2') sim.setSpeed(5)
    else if (e.key === '3') sim.setSpeed(20)
  })
  appState.subscribe((s, prev) => {
    if (s.sessionId && s.sessionId !== prev.sessionId) igniteCenter()
  })

  await sim.start(meta.id)
}

main().catch((e) => {
  app.textContent = `Error: ${e.message}`
  console.error(e)
})
