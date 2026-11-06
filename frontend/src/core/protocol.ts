
export const PROTOCOL_VERSION = 1
export const HEADER_SIZE = 16

export const BURNING_T_U8 = 100
export const BURNT_BETA_U8 = 25

export interface Frame {
  frame: number
  t: number
  nx: number
  ny: number
  version: number
  T: Uint8Array // row-major
  beta: Uint8Array
}

export function decodeFrame(buf: ArrayBuffer): Frame {
  if (buf.byteLength < HEADER_SIZE) throw new Error('frame shorter than header')
  const v = new DataView(buf)
  const frame = v.getUint32(0, true)
  const t = v.getFloat32(4, true)
  const nx = v.getUint16(8, true)
  const ny = v.getUint16(10, true)
  const version = v.getUint8(12)
  if (version !== PROTOCOL_VERSION) throw new Error(`unsupported protocol version ${version}`)
  const n = nx * ny
  if (buf.byteLength !== HEADER_SIZE + 2 * n) {
    throw new Error(`expected ${HEADER_SIZE + 2 * n} bytes, got ${buf.byteLength}`)
  }
  return {
    frame, t, nx, ny, version,
    T: new Uint8Array(buf, HEADER_SIZE, n),
    beta: new Uint8Array(buf, HEADER_SIZE + n, n),
  }
}

export type CellState = 'unburnt' | 'burning' | 'burnt'

export function cellState(T: number, beta: number): CellState {
  if (T >= BURNING_T_U8) return 'burning'
  if (beta <= BURNT_BETA_U8) return 'burnt'
  return 'unburnt'
}

export type Speed = 1 | 5 | 20
export const SPEEDS: readonly Speed[] = [1, 5, 20]
export type SimState = 'idle' | 'running' | 'paused' | 'finished'

export interface Metrics {
  t: number
  burned_area: number
  burned_trees: number
  front_speed: number
  T_max: number
}

export interface ParamSpec {
  name: string
  min: number
  max: number
  default: number
  live: boolean
  label?: string
  step?: number
  unit?: string
}

export interface PresetInfo {
  id: string
  name: string
  description: string
}

export type ClientMsg =
  | { type: 'start'; scene_id: string; params: Record<string, number> }
  | { type: 'pause' }
  | { type: 'resume' }
  | { type: 'reset' }
  | { type: 'ignite'; x: number; y: number }
  | { type: 'set_param'; name: string; value: number }
  | { type: 'set_speed'; speed: Speed }

export type ServerMsg =
  | { type: 'session'; id: string }
  | { type: 'metrics'; frame: number; metrics: Metrics }
  | { type: 'state'; state: SimState; speed: Speed }
  | { type: 'error'; message: string }
