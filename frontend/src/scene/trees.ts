import * as THREE from 'three'
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js'
import { cellState, type CellState, type Frame } from '../core/protocol'
import type { Terrain } from './terrain'

const LEAF = new THREE.Color('#2f6b2a')
const BURNT = new THREE.Color('#1c1a19')
const FLAME_A = new THREE.Color('#ff5a10')
const FLAME_B = new THREE.Color('#ffc23a')
const TRUNK = new THREE.Color('#5b4030')
const BURNT_SCALE = 0.55 // canopy shrinks once burnt

// Visual variation only. The crown radius is never changed: the solver uses it as fuel.
const MAX_TILT = THREE.MathUtils.degToRad(5)
const CANOPY_FRAC = [0.62, 0.85] // canopy share of the tree height (slender vs. squat)
const TIER_WEIGHTS = [0.35, 0.4, 0.25] // 1, 2 or 3 stacked cones, same pine family

const STATE_CODE: Record<CellState, number> = { unburnt: 0, burning: 1, burnt: 2 }

// Unit-height, unit-radius canopy with `tiers` stacked cones, base at y = 0.
function canopyGeometry(tiers: number): THREE.BufferGeometry {
  if (tiers === 1) return new THREE.ConeGeometry(1, 1, 7).translate(0, 0.5, 0)
  const parts: THREE.BufferGeometry[] = []
  for (let t = 0; t < tiers; t++) {
    const radius = 1 - t * (0.55 / tiers)
    const height = 1.6 / (tiers + 0.6)
    const base = (t * (1 - height)) / (tiers - 1)
    const cone = new THREE.ConeGeometry(radius, height, 7)
    cone.rotateY(t * 0.45)
    parts.push(cone.translate(0, base + height / 2, 0))
  }
  const merged = mergeGeometries(parts)
  parts.forEach((p) => p.dispose())
  return merged
}

/** Canopies (one InstancedMesh per tier count) and trunks; colour follows the tree's cell state. */
export class Trees {
  readonly group = new THREE.Group()
  readonly count: number
  private canopies: THREE.InstancedMesh[]
  private trunk: THREE.InstancedMesh
  private meshOf: Uint8Array // which canopy mesh holds tree k
  private slot: Uint32Array // instance index inside that mesh
  private cell: Uint32Array
  private state: Uint8Array
  private leaf: Float32Array // per-tree green
  private burning: number[] = []
  private matrices: THREE.Matrix4[] = []
  private dirtyColor = new Set<THREE.InstancedMesh>()
  private dirtyMatrix = new Set<THREE.InstancedMesh>()
  private tmp = new THREE.Color()

  constructor(trees: Float32Array, terrain: Terrain) {
    const n = (this.count = trees.length / 4)
    this.meshOf = new Uint8Array(n)
    this.slot = new Uint32Array(n)
    this.cell = new Uint32Array(n)
    this.state = new Uint8Array(n)
    this.leaf = new Float32Array(n * 3)

    // Each tree draws from its own position, so the look is stable per scene and seed.
    const rngs = Array.from({ length: n }, (_, k) => mulberry32(hash(trees[k * 4], trees[k * 4 + 1])))
    const sizes = [0, 0, 0]
    for (let k = 0; k < n; k++) {
      const u = rngs[k]()
      const tier = u < TIER_WEIGHTS[0] ? 0 : u < TIER_WEIGHTS[0] + TIER_WEIGHTS[1] ? 1 : 2
      this.meshOf[k] = tier
      this.slot[k] = sizes[tier]++
    }
    this.canopies = sizes.map((size, t) => {
      const mesh = new THREE.InstancedMesh(canopyGeometry(t + 1), new THREE.MeshLambertMaterial(), Math.max(size, 1))
      mesh.count = size
      mesh.castShadow = true
      return mesh
    })
    const trunkGeo = new THREE.CylinderGeometry(0.6, 1, 1, 5).translate(0, 0.5, 0)
    this.trunk = new THREE.InstancedMesh(trunkGeo, new THREE.MeshLambertMaterial(), Math.max(n, 1))
    this.trunk.count = n

    const up = new THREE.Vector3(0, 1, 0)
    const tiltAxis = new THREE.Vector3()
    const q = new THREE.Quaternion()
    const spin = new THREE.Quaternion()
    const m = new THREE.Matrix4()
    for (let k = 0; k < n; k++) {
      const [x, y, h, r] = trees.subarray(k * 4, k * 4 + 4)
      const rng = rngs[k]
      const ground = terrain.heightAt(x, y) - 0.2
      const canopyFrac = CANOPY_FRAC[0] + rng() * (CANOPY_FRAC[1] - CANOPY_FRAC[0])
      const trunkH = (1 - canopyFrac) * h + 0.1 * h
      const az = rng() * Math.PI * 2
      tiltAxis.set(Math.cos(az), 0, Math.sin(az))
      q.setFromAxisAngle(tiltAxis, rng() * MAX_TILT)
      spin.setFromAxisAngle(up, rng() * Math.PI * 2)
      q.multiply(spin)
      const base = new THREE.Vector3(x, ground, y)

      m.compose(base, q, new THREE.Vector3(0.12 * r * (0.8 + rng() * 0.4), trunkH, 0.12 * r))
      this.trunk.setMatrixAt(k, m)
      this.tmp.copy(TRUNK).offsetHSL((rng() - 0.5) * 0.04, (rng() - 0.5) * 0.1, (rng() - 0.5) * 0.08)
      this.trunk.setColorAt(k, this.tmp)

      // Canopy starts up the (tilted) trunk.
      const lift = new THREE.Vector3(0, (1 - canopyFrac) * h, 0).applyQuaternion(q)
      const cm = new THREE.Matrix4().compose(base.clone().add(lift), q, new THREE.Vector3(r, canopyFrac * h, r))
      this.matrices.push(cm)
      this.setMatrix(k, cm)

      this.tmp.copy(LEAF).offsetHSL((rng() - 0.5) * 0.08, (rng() - 0.5) * 0.25, (rng() - 0.5) * 0.12)
      this.leaf.set([this.tmp.r, this.tmp.g, this.tmp.b], k * 3)
      this.setColor(k, this.tmp)
      this.cell[k] = terrain.cellIndex(x, y)
    }
    for (const c of this.canopies) c.instanceColor?.setUsage(THREE.DynamicDrawUsage)
    this.group.add(...this.canopies, this.trunk)
    this.flush()
  }

  update(frame: Frame): void {
    if (!this.count) return
    const { T, beta } = frame
    this.burning = []
    for (let k = 0; k < this.count; k++) {
      const i = this.cell[k]
      const s = STATE_CODE[cellState(T[i], beta[i])]
      if (s === 1) this.burning.push(k)
      if (s === this.state[k]) continue
      const prev = this.state[k]
      this.state[k] = s
      if (s === 2 || prev === 2) this.setMatrix(k, s === 2 ? this.shrunk(k) : this.matrices[k])
      if (s === 0) this.setColor(k, this.tmp.fromArray(this.leaf, k * 3))
      if (s === 2) this.setColor(k, BURNT)
    }
    this.flush()
  }

  /** Flicker of burning canopies, called every render frame. */
  animate(time: number): void {
    if (!this.burning.length) return
    for (const k of this.burning) {
      const f = 0.5 + 0.5 * Math.sin(time * 9 + k * 1.7)
      this.setColor(k, this.tmp.copy(FLAME_A).lerp(FLAME_B, f))
    }
    this.flush()
  }

  /** Restores every tree to unburnt (new session on the same scene). */
  reset(): void {
    for (let k = 0; k < this.count; k++) {
      this.state[k] = 0
      this.setMatrix(k, this.matrices[k])
      this.setColor(k, this.tmp.fromArray(this.leaf, k * 3))
    }
    this.burning = []
    this.flush()
  }

  private setColor(k: number, c: THREE.Color): void {
    const mesh = this.canopies[this.meshOf[k]]
    mesh.setColorAt(this.slot[k], c)
    this.dirtyColor.add(mesh)
  }

  private setMatrix(k: number, m: THREE.Matrix4): void {
    const mesh = this.canopies[this.meshOf[k]]
    mesh.setMatrixAt(this.slot[k], m)
    this.dirtyMatrix.add(mesh)
  }

  private flush(): void {
    for (const mesh of this.dirtyColor) if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
    for (const mesh of this.dirtyMatrix) mesh.instanceMatrix.needsUpdate = true
    this.dirtyColor.clear()
    this.dirtyMatrix.clear()
  }

  private shrunk(k: number): THREE.Matrix4 {
    const p = new THREE.Vector3()
    const q = new THREE.Quaternion()
    const s = new THREE.Vector3()
    this.matrices[k].decompose(p, q, s)
    return new THREE.Matrix4().compose(p, q, s.multiplyScalar(BURNT_SCALE))
  }

  dispose(): void {
    for (const mesh of [...this.canopies, this.trunk]) {
      mesh.geometry.dispose()
      ;(mesh.material as THREE.Material).dispose()
      mesh.dispose()
    }
  }
}

function hash(x: number, y: number): number {
  let h = Math.imul(Math.round(x * 1000), 0x9e3779b1) ^ Math.imul(Math.round(y * 1000), 0x85ebca77)
  h ^= h >>> 15
  return Math.imul(h, 0xc2b2ae3d) >>> 0
}

// Small seeded RNG so the variation is stable per scene.
function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
