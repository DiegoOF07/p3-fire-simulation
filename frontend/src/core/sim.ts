import { buildScene, exportUrl, findScene, getParams, type SceneRequest } from './api'
import type { ClientMsg, Speed } from './protocol'
import { SimSocket } from './socket'
import { appState, type AppState, type Store } from './state'

/** Commands for the UI; server replies land in the store. */
export class SimController {
  constructor(
    private store: Store<AppState> = appState,
    private socket: SimSocket = new SimSocket(),
  ) {
    // Frames still in flight from a stopped session are dropped.
    socket.onFrame((frame) => {
      if (store.get().simState !== 'idle') store.set({ frame })
    })
    // Without a session id, state/metrics are late replies from a stopped session.
    socket.onMessage((m) => {
      const active = store.get().sessionId !== null
      switch (m.type) {
        case 'session':
          store.set({ sessionId: m.id, frame: null, metrics: null, error: null })
          break
        case 'state':
          if (active) store.set({ simState: m.state, speed: m.speed })
          break
        case 'metrics':
          if (active) store.set({ metrics: m.metrics })
          break
        case 'error':
          store.set({ error: m.message })
          break
      }
    })
    socket.onConnection(({ status, reconnected }) => {
      store.set({ connection: status })
      if (reconnected) this.recover().catch((e) => store.set({ error: String(e) }))
    })
  }

  /** Loads param specs; keeps values already set that are still valid. */
  async init(): Promise<void> {
    const specs = await getParams()
    const current = this.store.get().params
    const params = Object.fromEntries(specs.map((s) => [s.name, current[s.name] ?? s.default]))
    this.store.set({ paramSpecs: specs, params })
  }

  /** Builds a scene and leaves the simulation idle, ready to start. */
  async loadScene(req: SceneRequest): Promise<void> {
    this.pause()
    this.store.set({ simState: 'idle', sessionId: null, frame: null, metrics: null })
    const scene = await buildScene(req)
    this.store.set({ scene, sceneRequest: req, error: null })
  }

  async start(): Promise<void> {
    const { scene, params, speed } = this.store.get()
    if (!scene) throw new Error('load a scene first')
    await this.socket.whenOpen()
    this.send({ type: 'start', scene_id: scene.id, params })
    if (speed !== 1) this.send({ type: 'set_speed', speed })
  }

  // Session commands need a live session id, so they never reach a stopped session.
  pause = () => this.sendToSession({ type: 'pause' })
  resume = () => this.sendToSession({ type: 'resume' })
  reset = () => this.sendToSession({ type: 'reset' })
  ignite = (x: number, y: number) => this.sendToSession({ type: 'ignite', x, y })

  /** While idle it's stored and applied on start. */
  setSpeed(speed: Speed): void {
    if (this.store.get().simState === 'idle') this.store.set({ speed })
    else this.send({ type: 'set_speed', speed })
  }

  /** Non-live params can only change while idle. */
  canEdit(name: string): boolean {
    const { paramSpecs, simState } = this.store.get()
    const spec = paramSpecs.find((s) => s.name === name)
    return !!spec && (spec.live || simState === 'idle')
  }

  /** Before start the value is only stored and sent with start. */
  setParam(name: string, value: number): boolean {
    if (!this.canEdit(name)) {
      this.store.set({ error: `${name} solo se puede cambiar antes de iniciar` })
      return false
    }
    const { params, simState } = this.store.get()
    this.store.set({ params: { ...params, [name]: value } })
    if (simState !== 'idle') this.send({ type: 'set_param', name, value })
    return true
  }

  exportCsv(): void {
    const { sessionId } = this.store.get()
    if (!sessionId) return
    const a = document.createElement('a')
    a.href = exportUrl(sessionId)
    a.download = `session-${sessionId}.csv`
    a.click()
  }

  private sendToSession(msg: ClientMsg): void {
    if (this.store.get().sessionId) this.send(msg)
  }

  private send(msg: ClientMsg): void {
    if (!this.socket.send(msg)) this.store.set({ error: 'sin conexión con el servidor' })
  }

  // After a drop: back to idle; rebuild the scene if the server lost it.
  private async recover(): Promise<void> {
    this.store.set({ simState: 'idle', error: null })
    await this.init()
    const { scene, sceneRequest } = this.store.get()
    if (scene && sceneRequest && !(await findScene(scene.id))) {
      this.store.set({ scene: await buildScene(sceneRequest) })
    }
  }
}
