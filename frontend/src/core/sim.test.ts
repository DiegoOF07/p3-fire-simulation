import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ClientMsg, Frame, ServerMsg } from './protocol'
import { SimController } from './sim'
import type { ConnectionEvent, SimSocket } from './socket'
import { createStore, type AppState } from './state'

class FakeSocket {
  sent: ClientMsg[] = []
  open = true
  frame?: (f: Frame) => void
  message?: (m: ServerMsg) => void
  connection?: (e: ConnectionEvent) => void
  send(msg: ClientMsg) {
    if (this.open) this.sent.push(msg)
    return this.open
  }
  whenOpen = () => Promise.resolve()
  onFrame(l: (f: Frame) => void) { this.frame = l }
  onMessage(l: (m: ServerMsg) => void) { this.message = l }
  onConnection(l: (e: ConnectionEvent) => void) { this.connection = l }
}

const SPECS = [
  { name: 'spread_speed', min: 0, max: 5, default: 1, live: true },
  { name: 'grid', min: 50, max: 400, default: 200, live: false },
]
const SCENE = { id: 'scene1', nx: 2, ny: 2, cell_size: 1, n_trees: 0 }
const FRAME = { frame: 1, t: 0, nx: 2, ny: 2, version: 1, T: new Uint8Array(4), beta: new Uint8Array(4) }

function initialState(): AppState {
  return {
    connection: 'open', sceneRequest: null, scene: null, sessionId: null, simState: 'idle',
    speed: 1, paramSpecs: [], params: {}, frame: null, metrics: null, error: null,
  }
}

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }))
}

let fetchMock: ReturnType<typeof vi.fn>
let store: ReturnType<typeof createStore<AppState>>
let socket: FakeSocket
let sim: SimController

beforeEach(async () => {
  fetchMock = vi.fn((url: string) => {
    if (url === '/api/params') return jsonResponse(SPECS)
    if (url === '/api/scenes/build') return jsonResponse({ ...SCENE, id: `built-${fetchMock.mock.calls.length}` })
    return jsonResponse({ detail: 'not found' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  store = createStore(initialState())
  socket = new FakeSocket()
  sim = new SimController(store, socket as unknown as SimSocket)
  await sim.init()
  await sim.loadScene({ preset: 'flat', density: 1, seed: 0 })
})

afterEach(() => vi.unstubAllGlobals())

function startSession(id = 's1') {
  socket.message!({ type: 'session', id })
  socket.message!({ type: 'state', state: 'running', speed: 1 })
}

describe('SimController', () => {
  it('loads defaults and sends them with start', async () => {
    expect(store.get().params).toEqual({ spread_speed: 1, grid: 200 })
    sim.setParam('grid', 300)
    sim.setSpeed(20)
    await sim.start()
    expect(socket.sent).toEqual([
      { type: 'start', scene_id: store.get().scene!.id, params: { spread_speed: 1, grid: 300 } },
      { type: 'set_speed', speed: 20 },
    ])
  })

  it('blocks non-live params once started', () => {
    startSession()
    expect(sim.setParam('grid', 100)).toBe(false)
    expect(store.get().error).toMatch(/antes de iniciar/)
    expect(sim.setParam('spread_speed', 2)).toBe(true)
    expect(socket.sent).toContainEqual({ type: 'set_param', name: 'spread_speed', value: 2 })
  })

  it('sends session commands as soon as the session id arrives', () => {
    socket.message!({ type: 'session', id: 's1' })
    sim.ignite(1, 1)
    expect(socket.sent).toEqual([{ type: 'ignite', x: 1, y: 1 }])
  })

  it('ignores session commands and stale frames while idle', () => {
    sim.resume()
    sim.reset()
    sim.ignite(1, 1)
    expect(socket.sent).toEqual([])
    socket.frame!(FRAME)
    expect(store.get().frame).toBeNull()
  })

  it('drops late replies from the session it stopped', async () => {
    startSession()
    await sim.loadScene({ preset: 'flat', density: 1, seed: 1 })
    expect(socket.sent).toContainEqual({ type: 'pause' })
    socket.message!({ type: 'state', state: 'paused', speed: 1 })
    socket.frame!(FRAME)
    expect(store.get().simState).toBe('idle')
    expect(store.get().frame).toBeNull()
  })

  it('reconnects to idle and rebuilds a lost scene', async () => {
    startSession()
    const lost = store.get().scene!.id
    socket.connection!({ status: 'reconnecting', reconnected: false })
    expect(store.get().connection).toBe('reconnecting')
    socket.connection!({ status: 'open', reconnected: true })
    await vi.waitFor(() => expect(store.get().scene!.id).not.toBe(lost))
    expect(store.get().simState).toBe('idle')
    expect(store.get().params.spread_speed).toBe(1)
  })

  it('reports commands sent while disconnected', () => {
    startSession()
    socket.open = false
    sim.pause()
    expect(store.get().error).toMatch(/sin conexión/)
  })
})
