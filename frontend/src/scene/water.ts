import * as THREE from 'three'
import type { Terrain } from './terrain'
import type { Wind } from './wind'

// Presets whose carved channel holds water. Visual only: the solver still sees ground fuel there.
export const WATER_PRESETS = new Set(['river_slope'])

const BLUR_RADIUS = 8 // cells
const DEPTH_MIN = 0.5 // m below the local mean: water edge (alpha 0)
const DEPTH_FULL = 0.9 // m: fully opaque water
const SURFACE = 0.35 // m above the channel bed

const vertexShader = /* glsl */ `
  attribute float alpha;
  varying float vAlpha;
  varying vec2 vXZ;
  varying vec3 vWorld;
  uniform float uTime;
  uniform float uChop;
  void main() {
    vAlpha = alpha;
    vec3 p = position;
    // Small swell, stronger with wind.
    p.y += (0.04 + 0.05 * uChop) * sin(p.x * 0.9 + uTime * 2.1) * cos(p.z * 0.7 - uTime * 1.6);
    vXZ = p.xz;
    vec4 world = modelMatrix * vec4(p, 1.0);
    vWorld = world.xyz;
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`

const fragmentShader = /* glsl */ `
  varying float vAlpha;
  varying vec2 vXZ;
  varying vec3 vWorld;
  uniform float uTime;
  uniform vec2 uFlow;   // m/s, downhill current
  uniform vec2 uWind;   // m/s, surface drift from wind
  uniform float uChop;  // 0..1 wind strength
  uniform vec3 uDeep;
  uniform vec3 uShallow;
  uniform vec3 uFoam;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
  }

  void main() {
    // Two ripple layers: one carried by the current, one pushed by the wind.
    vec2 a = vXZ * 0.45 - uFlow * uTime * 0.45;
    vec2 b = vXZ * (0.8 + 0.6 * uChop) - (uFlow * 0.6 + uWind) * uTime * 0.8;
    float n = noise(a) * 0.55 + noise(b) * (0.45 + 0.3 * uChop);
    float streak = smoothstep(0.62 - 0.12 * uChop, 0.95, n);

    vec3 col = mix(uShallow, uDeep, smoothstep(0.2, 1.0, vAlpha));
    col = mix(col, uShallow * 1.25, n * 0.35);
    col = mix(col, uFoam, streak * 0.55);
    // Fake sky glint, stronger when looking along the surface.
    vec3 view = normalize(cameraPosition - vWorld);
    float fresnel = pow(1.0 - clamp(view.y, 0.0, 1.0), 3.0);
    col = mix(col, vec3(0.85, 0.93, 1.0), fresnel * 0.45);
    // Foam where the water meets the bank.
    col = mix(uFoam, col, smoothstep(0.0, 0.35, vAlpha));
    gl_FragColor = vec4(col, clamp(vAlpha * 1.6, 0.0, 0.92));
  }
`

/** Animated water over the carved river channel, found from the heightmap. */
export class Water {
  readonly mesh: THREE.Mesh | null = null
  private material: THREE.ShaderMaterial | null = null

  constructor(heights: Float32Array, terrain: Terrain) {
    const { nx, ny, cellSize } = terrain
    const depth = localDepth(heights, nx, ny, BLUR_RADIUS)
    const alpha = new Float32Array(nx * ny)
    for (let i = 0; i < alpha.length; i++) {
      alpha[i] = THREE.MathUtils.smoothstep(depth[i], DEPTH_MIN, DEPTH_FULL)
    }
    // Keep a triangle when any corner is wet, so the edge fades instead of clipping.
    const index: number[] = []
    for (let r = 0; r < ny - 1; r++) {
      for (let c = 0; c < nx - 1; c++) {
        const a = r * nx + c
        const b = a + 1
        const d = a + nx
        const e = d + 1
        if (alpha[a] + alpha[b] + alpha[d] + alpha[e] > 0) index.push(a, d, b, b, d, e)
      }
    }
    if (!index.length) return

    // Flat water level per cell: the channel bed plus a little, smoothed so it doesn't ripple with the bed.
    const level = boxBlur(heights, nx, ny, 2)
    const pos = new Float32Array(nx * ny * 3)
    for (let r = 0; r < ny; r++) {
      for (let c = 0; c < nx; c++) {
        const i = r * nx + c
        pos.set([(c + 0.5) * cellSize, Math.min(level[i], heights[i] + 0.6) + SURFACE, (r + 0.5) * cellSize], i * 3)
      }
    }
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    geometry.setAttribute('alpha', new THREE.BufferAttribute(alpha, 1))
    geometry.setIndex(index)

    // Current flows downhill: average terrain gradient over the wet cells.
    const flow = downhill(heights, alpha, nx, ny)
    this.material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      transparent: true,
      depthWrite: false,
      uniforms: {
        uTime: { value: 0 },
        uFlow: { value: flow },
        uWind: { value: new THREE.Vector2() },
        uChop: { value: 0 },
        uDeep: { value: new THREE.Color('#1f6fa8') },
        uShallow: { value: new THREE.Color('#5cc6e8') },
        uFoam: { value: new THREE.Color('#e6f6ff') },
      },
    })
    this.mesh = new THREE.Mesh(geometry, this.material)
    this.mesh.renderOrder = 1
  }

  animate(time: number, wind: Wind): void {
    if (!this.material) return
    const u = this.material.uniforms
    u.uTime.value = time
    // Wind drags the surface at a few percent of its speed; sim +y is world +z.
    ;(u.uWind.value as THREE.Vector2).set(Math.cos(wind.dir), Math.sin(wind.dir)).multiplyScalar(wind.speed * 0.12)
    u.uChop.value = THREE.MathUtils.clamp(wind.speed / 12, 0, 1)
  }

  dispose(): void {
    this.mesh?.geometry.dispose()
    this.material?.dispose()
  }
}

function boxBlur(src: Float32Array, nx: number, ny: number, r: number): Float32Array {
  const tmp = new Float32Array(src.length)
  const out = new Float32Array(src.length)
  const w = 2 * r + 1
  for (let row = 0; row < ny; row++) {
    for (let c = 0; c < nx; c++) {
      let s = 0
      for (let k = -r; k <= r; k++) s += src[row * nx + THREE.MathUtils.clamp(c + k, 0, nx - 1)]
      tmp[row * nx + c] = s / w
    }
  }
  for (let row = 0; row < ny; row++) {
    for (let c = 0; c < nx; c++) {
      let s = 0
      for (let k = -r; k <= r; k++) s += tmp[THREE.MathUtils.clamp(row + k, 0, ny - 1) * nx + c]
      out[row * nx + c] = s / w
    }
  }
  return out
}

// How far each cell sits below its neighbourhood mean (m); positive inside channels.
function localDepth(h: Float32Array, nx: number, ny: number, r: number): Float32Array {
  const mean = boxBlur(h, nx, ny, r)
  return mean.map((m, i) => m - h[i])
}

// The current runs along the river (its longer extent), towards the lower end.
function downhill(h: Float32Array, alpha: Float32Array, nx: number, ny: number): THREE.Vector2 {
  let c0 = nx, c1 = 0, r0 = ny, r1 = 0
  for (let i = 0; i < alpha.length; i++) {
    if (alpha[i] < 0.5) continue
    const r = Math.floor(i / nx)
    const c = i % nx
    c0 = Math.min(c0, c); c1 = Math.max(c1, c)
    r0 = Math.min(r0, r); r1 = Math.max(r1, r)
  }
  if (c1 < c0) return new THREE.Vector2()
  const alongX = c1 - c0 >= r1 - r0
  // Mean wet height in the first and last tenth of the course.
  let lowSum = 0, lowN = 0, highSum = 0, highN = 0
  for (let i = 0; i < alpha.length; i++) {
    if (alpha[i] < 0.5) continue
    const t = alongX ? ((i % nx) - c0) / (c1 - c0 || 1) : (Math.floor(i / nx) - r0) / (r1 - r0 || 1)
    if (t < 0.1) { lowSum += h[i]; lowN++ }
    if (t > 0.9) { highSum += h[i]; highN++ }
  }
  const sign = lowN && highN && lowSum / lowN < highSum / highN ? -1 : 1
  return alongX ? new THREE.Vector2(1.2 * sign, 0) : new THREE.Vector2(0, 1.2 * sign)
}
