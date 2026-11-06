import { buildScene } from './core/api'
import { SimSocket } from './core/socket'
import { FlatView } from './preview/flatView'

const app = document.querySelector<HTMLDivElement>('#app')!

async function main() {
  const meta = await buildScene('flat')
  const view = new FlatView(app, meta.nx, meta.ny, meta.cell_size)
  const socket = new SimSocket()
  socket.onFrame((f) => view.update(f))
  socket.onMessage((m) => {
    if (m.type === 'error') console.error(m.message)
  })
  await socket.ready
  socket.send({ type: 'start', scene_id: meta.id, params: {} })
  const half = (n: number) => (n * meta.cell_size) / 2
  socket.send({ type: 'ignite', x: half(meta.nx), y: half(meta.ny) })
}

main().catch((e) => {
  app.textContent = `Error: ${e.message}`
  console.error(e)
})
