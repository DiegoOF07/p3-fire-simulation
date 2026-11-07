import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { Frame } from '../core/protocol'

const FUEL = [46, 110, 40]
const ASH = [35, 32, 30]
const FIRE = [255, 140, 20]
const HEAT_FULL = 160 // T code drawn as full fire color

export class FlatView {
  private renderer = new THREE.WebGLRenderer({ antialias: true })
  private scene = new THREE.Scene()
  private camera = new THREE.PerspectiveCamera(50, 1, 1, 5000)
  private controls: OrbitControls
  private texture: THREE.DataTexture
  private pixels: Uint8Array<ArrayBuffer>
  private resizer: ResizeObserver

  constructor(container: HTMLElement, nx: number, ny: number, cellSize: number) {
    const width = nx * cellSize
    const depth = ny * cellSize
    container.appendChild(this.renderer.domElement)
    this.scene.background = new THREE.Color(0x111111)

    this.pixels = new Uint8Array(nx * ny * 4)
    for (let i = 0; i < nx * ny; i++) this.pixels.set([...FUEL, 255], i * 4)
    this.texture = new THREE.DataTexture(this.pixels, nx, ny)
    this.texture.colorSpace = THREE.SRGBColorSpace
    this.texture.magFilter = THREE.LinearFilter

    // Sim (x, y) -> world (x, 0, y), origin at the grid corner.
    const geometry = new THREE.PlaneGeometry(width, depth)
    geometry.rotateX(-Math.PI / 2)
    geometry.translate(width / 2, 0, depth / 2)
    const uv = geometry.attributes.uv
    for (let i = 0; i < uv.count; i++) uv.setY(i, 1 - uv.getY(i))
    this.scene.add(new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ map: this.texture })))

    const center = new THREE.Vector3(width / 2, 0, depth / 2)
    this.camera.position.set(width / 2, Math.max(width, depth) * 0.9, depth * 1.4)
    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.controls.target.copy(center)
    this.controls.enableDamping = true

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = container
      this.renderer.setSize(w, h)
      this.renderer.setPixelRatio(window.devicePixelRatio)
      this.camera.aspect = w / h
      this.camera.updateProjectionMatrix()
    }
    this.resizer = new ResizeObserver(resize)
    this.resizer.observe(container)
    resize()
    this.renderer.setAnimationLoop(() => {
      this.controls.update()
      this.renderer.render(this.scene, this.camera)
    })
  }

  dispose(): void {
    this.renderer.setAnimationLoop(null)
    this.resizer.disconnect()
    this.controls.dispose()
    this.texture.dispose()
    this.scene.traverse((o) => {
      if (o instanceof THREE.Mesh) {
        o.geometry.dispose()
        o.material.dispose()
      }
    })
    this.renderer.dispose()
    this.renderer.domElement.remove()
  }

  update(frame: Frame): void {
    if (frame.T.length * 4 !== this.pixels.length) return
    const { T, beta } = frame
    const pixels = this.pixels
    for (let i = 0; i < T.length; i++) {
      const fuel = beta[i] / 255
      const heat = Math.min(1, T[i] / HEAT_FULL)
      for (let c = 0; c < 3; c++) {
        const ground = ASH[c] + (FUEL[c] - ASH[c]) * fuel
        pixels[i * 4 + c] = ground + (FIRE[c] - ground) * heat
      }
      pixels[i * 4 + 3] = 255
    }
    this.texture.needsUpdate = true
  }
}
