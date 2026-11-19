import * as THREE from 'three'
import { BURNT_BETA_U8, type Frame } from '../core/protocol'

const GRASS = new THREE.Color('#8a9a4a')
const FOREST_FLOOR = new THREE.Color('#3f5a2a')
const ASH = new THREE.Color('#2b2826')
const ISO_LINE = new THREE.Color('#f2e2a6')
// Fire ramp by T code: dull red near "burning" (100) to yellow-white at the top.
const FIRE_STOPS: [number, THREE.Color][] = [
  [60, new THREE.Color('#5a1205')],
  [110, new THREE.Color('#d0300a')],
  [170, new THREE.Color('#ff8a1a')],
  [255, new THREE.Color('#fff1a0')],
]
const HEAT_START = 40 // T code where the glow starts

const fireLUT = buildFireLUT()

function buildFireLUT(): Float32Array {
  const lut = new Float32Array(256 * 4) // r, g, b, glow weight
  const c = new THREE.Color()
  for (let t = 0; t < 256; t++) {
    let k = 0
    while (k < FIRE_STOPS.length - 2 && t > FIRE_STOPS[k + 1][0]) k++
    const [t0, c0] = FIRE_STOPS[k]
    const [t1, c1] = FIRE_STOPS[k + 1]
    c.copy(c0).lerp(c1, THREE.MathUtils.clamp((t - t0) / (t1 - t0), 0, 1))
    lut.set([c.r, c.g, c.b, THREE.MathUtils.clamp((t - HEAT_START) / 70, 0, 1)], t * 4)
  }
  return lut
}

/** Terrain mesh with one vertex per cell center, so vertex i is cell i (row * nx + col). */
export class Terrain {
  readonly mesh: THREE.Mesh
  readonly minHeight: number
  readonly maxHeight: number
  private colors: THREE.BufferAttribute
  private base: Float32Array // fuel color per cell before burning
  private beta0: Uint8Array | null = null
  private arrival: Float32Array // s when each cell became burnt, NaN if not yet
  private lastT = -1

  constructor(
    private heights: Float32Array,
    readonly nx: number,
    readonly ny: number,
    readonly cellSize: number,
    trees: Float32Array,
  ) {
    const n = nx * ny
    const pos = new Float32Array(n * 3)
    let min = Infinity
    let max = -Infinity
    for (let r = 0; r < ny; r++) {
      for (let c = 0; c < nx; c++) {
        const i = r * nx + c
        const h = heights[i]
        pos.set([(c + 0.5) * cellSize, h, (r + 0.5) * cellSize], i * 3)
        min = Math.min(min, h)
        max = Math.max(max, h)
      }
    }
    this.minHeight = min
    this.maxHeight = max

    const index = new Uint32Array((nx - 1) * (ny - 1) * 6)
    let k = 0
    for (let r = 0; r < ny - 1; r++) {
      for (let c = 0; c < nx - 1; c++) {
        const a = r * nx + c
        const b = a + 1
        const d = a + nx
        const e = d + 1
        index.set([a, d, b, b, d, e], k)
        k += 6
      }
    }

    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    geometry.setIndex(new THREE.BufferAttribute(index, 1))
    geometry.computeVertexNormals()
    this.colors = new THREE.BufferAttribute(new Float32Array(n * 3), 3)
    this.colors.setUsage(THREE.DynamicDrawUsage)
    geometry.setAttribute('color', this.colors)

    this.base = this.fuelColors(trees, min, max)
    this.arrival = new Float32Array(n).fill(NaN)
    this.colors.array.set(this.base)

    this.mesh = new THREE.Mesh(geometry, new THREE.MeshLambertMaterial({ vertexColors: true }))
    this.mesh.receiveShadow = true
  }

  get width() {
    return this.nx * this.cellSize
  }

  get depth() {
    return this.ny * this.cellSize
  }

  /** Bilinear height at sim (x, y) in metres. */
  heightAt(x: number, y: number): number {
    const fx = THREE.MathUtils.clamp(x / this.cellSize - 0.5, 0, this.nx - 1)
    const fy = THREE.MathUtils.clamp(y / this.cellSize - 0.5, 0, this.ny - 1)
    const c0 = Math.min(Math.floor(fx), this.nx - 2)
    const r0 = Math.min(Math.floor(fy), this.ny - 2)
    const tx = fx - c0
    const ty = fy - r0
    const h = this.heights
    const i = r0 * this.nx + c0
    const top = h[i] * (1 - tx) + h[i + 1] * tx
    const bottom = h[i + this.nx] * (1 - tx) + h[i + this.nx + 1] * tx
    return top * (1 - ty) + bottom * ty
  }

  cellIndex(x: number, y: number): number {
    const c = THREE.MathUtils.clamp(Math.floor(x / this.cellSize), 0, this.nx - 1)
    const r = THREE.MathUtils.clamp(Math.floor(y / this.cellSize), 0, this.ny - 1)
    return r * this.nx + c
  }

  /** Clears burn history (new session on the same scene). */
  resetBurn(): void {
    this.beta0 = null
    this.arrival.fill(NaN)
    this.lastT = -1
    this.colors.array.set(this.base)
    this.colors.needsUpdate = true
  }

  update(frame: Frame, isoInterval: number | null): void {
    const { T, beta } = frame
    if (T.length !== this.nx * this.ny) return
    if (frame.t < this.lastT) this.resetBurn()
    this.lastT = frame.t
    if (!this.beta0) this.beta0 = beta.slice()
    const beta0 = this.beta0
    const base = this.base
    const arrival = this.arrival
    const out = this.colors.array as Float32Array
    const nx = this.nx

    for (let i = 0; i < T.length; i++) {
      if (beta[i] <= BURNT_BETA_U8 && Number.isNaN(arrival[i]) && beta0[i] > BURNT_BETA_U8) arrival[i] = frame.t
      const f = beta0[i] > 0 ? Math.min(1, beta[i] / beta0[i]) : 1
      const o = i * 3
      let r = ASH.r + (base[o] - ASH.r) * f
      let g = ASH.g + (base[o + 1] - ASH.g) * f
      let b = ASH.b + (base[o + 2] - ASH.b) * f
      const l = T[i] * 4
      const w = fireLUT[l + 3]
      if (w > 0) {
        r += (fireLUT[l] - r) * w
        g += (fireLUT[l + 1] - g) * w
        b += (fireLUT[l + 2] - b) * w
      }
      out[o] = r
      out[o + 1] = g
      out[o + 2] = b
    }

    if (isoInterval) this.drawIsochrones(out, isoInterval, nx)
    this.colors.needsUpdate = true
  }

  // A cell is on a line when its arrival bucket differs from its right or lower neighbour.
  private drawIsochrones(out: Float32Array, interval: number, nx: number): void {
    const a = this.arrival
    const n = a.length
    for (let i = 0; i < n; i++) {
      const ai = a[i]
      if (Number.isNaN(ai)) continue
      const bucket = Math.floor(ai / interval)
      const right = (i + 1) % nx !== 0 ? a[i + 1] : NaN
      const down = i + nx < n ? a[i + nx] : NaN
      const edge =
        (!Number.isNaN(right) && Math.floor(right / interval) !== bucket) ||
        (!Number.isNaN(down) && Math.floor(down / interval) !== bucket)
      if (edge) out.set([ISO_LINE.r, ISO_LINE.g, ISO_LINE.b], i * 3)
    }
  }

  // Fuel look before the first frame: darker under crowns, slightly lighter up high.
  private fuelColors(trees: Float32Array, min: number, max: number): Float32Array {
    const { nx, ny, cellSize: cs } = this
    const cover = new Float32Array(nx * ny)
    for (let k = 0; k < trees.length; k += 4) {
      const x = trees[k]
      const y = trees[k + 1]
      const rad = trees[k + 3]
      const c0 = Math.max(0, Math.floor((x - rad) / cs))
      const c1 = Math.min(nx - 1, Math.floor((x + rad) / cs))
      const r0 = Math.max(0, Math.floor((y - rad) / cs))
      const r1 = Math.min(ny - 1, Math.floor((y + rad) / cs))
      for (let r = r0; r <= r1; r++) {
        for (let c = c0; c <= c1; c++) {
          if (Math.hypot((c + 0.5) * cs - x, (r + 0.5) * cs - y) <= rad) cover[r * nx + c] = 1
        }
      }
    }
    const out = new Float32Array(nx * ny * 3)
    const col = new THREE.Color()
    const span = max - min || 1
    for (let i = 0; i < nx * ny; i++) {
      col.copy(GRASS).lerp(FOREST_FLOOR, cover[i])
      col.offsetHSL(0, 0, 0.06 * ((this.heights[i] - min) / span))
      out.set([col.r, col.g, col.b], i * 3)
    }
    return out
  }

  dispose(): void {
    this.mesh.geometry.dispose()
    ;(this.mesh.material as THREE.Material).dispose()
  }
}
