import type { Speed } from './protocol'
import { SimSocket } from './socket'
import { appState, type AppState, type Store } from './state'

/** Commands for the UI; server replies land in the store. */
export class SimController {
  constructor(
    private store: Store<AppState> = appState,
    private socket: SimSocket = new SimSocket(),
  ) {
    socket.onFrame((frame) => store.set({ frame }))
    socket.onMessage((m) => {
      switch (m.type) {
        case 'session':
          store.set({ sessionId: m.id, frame: null, metrics: null, error: null })
          break
        case 'state':
          store.set({ simState: m.state, speed: m.speed })
          break
        case 'metrics':
          store.set({ metrics: m.metrics })
          break
        case 'error':
          store.set({ error: m.message })
          break
      }
    })
  }

  async start(sceneId: string): Promise<void> {
    await this.socket.ready
    this.socket.send({ type: 'start', scene_id: sceneId, params: this.store.get().params })
  }

  pause = () => this.socket.send({ type: 'pause' })
  resume = () => this.socket.send({ type: 'resume' })
  reset = () => this.socket.send({ type: 'reset' })
  ignite = (x: number, y: number) => this.socket.send({ type: 'ignite', x, y })
  setSpeed = (speed: Speed) => this.socket.send({ type: 'set_speed', speed })

  /** Before start the value is only stored and sent with start. */
  setParam(name: string, value: number): void {
    const { params, simState } = this.store.get()
    this.store.set({ params: { ...params, [name]: value } })
    if (simState !== 'idle') this.socket.send({ type: 'set_param', name, value })
  }
}
