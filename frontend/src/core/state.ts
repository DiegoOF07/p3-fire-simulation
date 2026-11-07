import type { SceneMeta } from './api'
import type { Frame, Metrics, SimState, Speed } from './protocol'

type Listener<T> = (state: T, prev: T) => void

export interface Store<T> {
  get(): T
  set(patch: Partial<T>): void
  subscribe(listener: Listener<T>): () => void
}

export function createStore<T extends object>(initial: T): Store<T> {
  let state = initial
  const listeners = new Set<Listener<T>>()
  return {
    get: () => state,
    set(patch) {
      const prev = state
      state = { ...state, ...patch }
      listeners.forEach((l) => l(state, prev))
    },
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
}

export interface AppState {
  scene: SceneMeta | null
  sessionId: string | null
  simState: SimState
  speed: Speed
  params: Record<string, number>
  frame: Frame | null
  metrics: Metrics | null
  error: string | null
}

export const appState = createStore<AppState>({
  scene: null,
  sessionId: null,
  simState: 'idle',
  speed: 1,
  params: {},
  frame: null,
  metrics: null,
  error: null,
})
