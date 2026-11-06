import type { ParamSpec, PresetInfo } from './protocol'

export interface SceneMeta {
  id: string
  nx: number
  ny: number
  cell_size: number
  n_trees: number
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(path, init)
  if (!res.ok) throw new Error(`${init?.method ?? 'GET'} ${path} -> ${res.status}`)
  return res
}

const json = async <T>(path: string, init?: RequestInit): Promise<T> => (await request(path, init)).json()
const f32 = async (path: string) => new Float32Array(await (await request(path)).arrayBuffer())

export const getParams = () => json<ParamSpec[]>('/api/params')
export const getPresets = () => json<PresetInfo[]>('/api/scenes')

export const buildScene = (preset: string, density = 1, seed = 0) =>
  json<SceneMeta>('/api/scenes/build', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ preset, density, seed }),
  })

// (ny * nx) heights, row-major
export const getHeightmap = (id: string) => f32(`/api/scenes/${id}/heightmap`)
// (n * 4): x, y, height, radius
export const getTrees = (id: string) => f32(`/api/scenes/${id}/trees`)
