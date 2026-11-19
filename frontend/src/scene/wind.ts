import * as THREE from 'three'

export interface Wind {
  speed: number // m/s, 0 when wind_mode = 0
  dir: number // rad, direction the wind blows towards, sim frame
}

// Same formulas as the solver (see integracion_solver.md), so arrows match the simulated wind.
export function windAt(params: Record<string, number>, t: number): Wind {
  const mode = Math.round(params.wind_mode ?? 0)
  const speed = params.wind_speed ?? 0
  const dirDeg = params.wind_dir ?? 0
  if (mode === 0) return { speed: 0, dir: 0 }
  if (mode === 1) return { speed, dir: THREE.MathUtils.degToRad(dirDeg) }
  const period = params.wind_period ?? 60
  const gust = params.wind_gust ?? 0
  const swing = params.wind_swing ?? 0
  return {
    speed: speed * (1 + gust * Math.sin((2 * Math.PI * t) / period)),
    dir: THREE.MathUtils.degToRad(dirDeg + swing * Math.sin((2 * Math.PI * t) / (1.7 * period))),
  }
}

const GRID = 4
const COLOR = 0x9ad1ff

export class WindArrows {
  readonly group = new THREE.Group()
  private arrows: THREE.ArrowHelper[] = []

  constructor(width: number, depth: number, height: number) {
    for (let i = 0; i < GRID; i++) {
      for (let j = 0; j < GRID; j++) {
        const origin = new THREE.Vector3(((i + 0.5) / GRID) * width, height, ((j + 0.5) / GRID) * depth)
        const a = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), origin, 10, COLOR, 3, 2)
        this.arrows.push(a)
        this.group.add(a)
      }
    }
  }

  update(wind: Wind, visible: boolean): void {
    this.group.visible = visible && wind.speed > 0
    if (!this.group.visible) return
    // Sim +y is world +z.
    const dir = new THREE.Vector3(Math.cos(wind.dir), 0, Math.sin(wind.dir))
    const length = 4 + 2 * wind.speed
    for (const a of this.arrows) {
      a.setDirection(dir)
      a.setLength(length, Math.min(4, length * 0.3), Math.min(3, length * 0.2))
    }
  }

  dispose(): void {
    for (const a of this.arrows) a.dispose()
  }
}
