import * as THREE from 'three'
import { BURNING_T_U8, type Frame } from '../core/protocol'
import type { Wind } from './wind'
import type { Terrain } from './terrain'

interface Layer {
  points: THREE.Points
  pos: Float32Array
  vel: Float32Array
  life: Float32Array
  maxLife: number
  rise: number
  next: number
}

const EMBERS = 1500
const SMOKE = 600

/** Embers and light smoke spawned over burning cells; purely visual. */
export class FireEffects {
  readonly group = new THREE.Group()
  private embers: Layer
  private smoke: Layer
  private burning: number[] = []
  private texture = makeDot()

  constructor(private terrain: Terrain) {
    this.embers = this.layer(EMBERS, 1.2, 2.2, new THREE.PointsMaterial({
      size: 0.9, color: 0xffa040, map: this.texture, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending,
    }))
    this.smoke = this.layer(SMOKE, 6, 1.5, new THREE.PointsMaterial({
      size: 9, color: 0x55514d, map: this.texture, transparent: true, opacity: 0.22, depthWrite: false,
    }))
  }

  private layer(n: number, maxLife: number, rise: number, mat: THREE.PointsMaterial): Layer {
    const pos = new Float32Array(n * 3).fill(-1e4)
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage))
    const points = new THREE.Points(geo, mat)
    points.frustumCulled = false
    this.group.add(points)
    return { points, pos, vel: new Float32Array(n * 3), life: new Float32Array(n), maxLife, rise, next: 0 }
  }

  /** Remembers burning cells from the latest frame. */
  update(frame: Frame): void {
    const T = frame.T
    const list: number[] = []
    for (let i = 0; i < T.length; i++) if (T[i] >= BURNING_T_U8) list.push(i)
    this.burning = list
  }

  animate(dt: number, wind: Wind): void {
    const wx = Math.cos(wind.dir) * wind.speed * 0.4
    const wz = Math.sin(wind.dir) * wind.speed * 0.4
    this.spawn(this.embers, dt * Math.min(400, this.burning.length * 0.6), 1.5)
    this.spawn(this.smoke, dt * Math.min(80, this.burning.length * 0.08), 0.6)
    this.advance(this.embers, dt, wx, wz)
    this.advance(this.smoke, dt, wx, wz)
  }

  clear(): void {
    this.burning = []
    for (const l of [this.embers, this.smoke]) {
      l.pos.fill(-1e4)
      l.life.fill(0)
      l.points.geometry.attributes.position.needsUpdate = true
    }
  }

  private spawn(l: Layer, amount: number, jitter: number): void {
    if (!this.burning.length) return
    const n = l.life.length
    let count = Math.floor(amount) + (Math.random() < amount % 1 ? 1 : 0)
    const t = this.terrain
    while (count-- > 0) {
      const cell = this.burning[(Math.random() * this.burning.length) | 0]
      const x = ((cell % t.nx) + Math.random()) * t.cellSize
      const y = (Math.floor(cell / t.nx) + Math.random()) * t.cellSize
      const k = l.next
      l.next = (l.next + 1) % n
      l.pos.set([x, t.heightAt(x, y) + 1 + Math.random() * 3, y], k * 3)
      l.vel.set([(Math.random() - 0.5) * jitter, l.rise * (0.6 + Math.random() * 0.8), (Math.random() - 0.5) * jitter], k * 3)
      l.life[k] = l.maxLife * (0.5 + Math.random() * 0.5)
    }
  }

  private advance(l: Layer, dt: number, wx: number, wz: number): void {
    const { pos, vel, life } = l
    for (let k = 0; k < life.length; k++) {
      if (life[k] <= 0) continue
      life[k] -= dt
      const o = k * 3
      if (life[k] <= 0) {
        pos[o + 1] = -1e4
        continue
      }
      pos[o] += (vel[o] + wx) * dt
      pos[o + 1] += vel[o + 1] * dt
      pos[o + 2] += (vel[o + 2] + wz) * dt
    }
    l.points.geometry.attributes.position.needsUpdate = true
  }

  dispose(): void {
    this.texture.dispose()
    for (const l of [this.embers, this.smoke]) {
      l.points.geometry.dispose()
      ;(l.points.material as THREE.Material).dispose()
    }
  }
}

function makeDot(): THREE.Texture {
  const c = document.createElement('canvas')
  c.width = c.height = 32
  const g = c.getContext('2d')!
  const grad = g.createRadialGradient(16, 16, 0, 16, 16, 16)
  grad.addColorStop(0, 'rgba(255,255,255,1)')
  grad.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = grad
  g.fillRect(0, 0, 32, 32)
  return new THREE.CanvasTexture(c)
}
