import type { ParamSpec, PresetInfo } from './protocol'

export interface SceneRequest {
  preset: string
  density: number
  seed: number
}

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

export const buildScene = (req: SceneRequest) =>
  json<SceneMeta>('/api/scenes/build', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

/** null when the server no longer has the scene (e.g. it restarted). */
export async function findScene(id: string): Promise<SceneMeta | null> {
  const res = await fetch(`/api/scenes/${id}`)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`GET /api/scenes/${id} -> ${res.status}`)
  return res.json()
}

export const exportUrl = (sessionId: string) => `/api/sessions/${sessionId}/export.csv`

// (ny * nx) heights, row-major
export const getHeightmap = (id: string) => f32(`/api/scenes/${id}/heightmap`)
// (n * 4): x, y, height, radius
export const getTrees = (id: string) => f32(`/api/scenes/${id}/trees`)
