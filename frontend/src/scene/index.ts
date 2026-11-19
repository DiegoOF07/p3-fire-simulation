import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { getHeightmap, getTrees, type SceneMeta } from '../core/api'
import type { SimController } from '../core/sim'
import { appState, type AppState } from '../core/state'
import { FireEffects } from './effects'
import { viewOptions } from './options'
import { Terrain } from './terrain'
import { Trees } from './trees'
import { WindArrows, windAt } from './wind'

const CLICK_TOLERANCE = 5 // px; more movement is an orbit drag, not a click

interface Loaded {
  id: string
  terrain: Terrain
  trees: Trees
  wind: WindArrows
  effects: FireEffects
  markers: THREE.Group
}

export function mountScene(container: HTMLElement, sim: SimController): void {
  const renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.shadowMap.enabled = true
  container.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  scene.background = new THREE.Color('#9fb6c8')
  scene.fog = new THREE.Fog('#9fb6c8', 300, 900)
  scene.add(new THREE.HemisphereLight('#dfeeff', '#4a3b2a', 1.6))
  const sun = new THREE.DirectionalLight('#fff4e0', 2.2)
  sun.castShadow = true
  sun.shadow.mapSize.set(2048, 2048)
  scene.add(sun, sun.target)

  const camera = new THREE.PerspectiveCamera(50, 1, 0.5, 3000)
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.maxPolarAngle = Math.PI * 0.48

  let current: Loaded | null = null
  let loading: string | null = null
  // Clicks made before a session exists; applied as soon as it starts.
  let pending: [number, number][] = []

  async function load(meta: SceneMeta) {
    loading = meta.id
    const [heights, treeData] = await Promise.all([getHeightmap(meta.id), getTrees(meta.id)])
    if (loading !== meta.id) return // a newer scene was requested meanwhile
    unload()
    const terrain = new Terrain(heights, meta.nx, meta.ny, meta.cell_size, treeData)
    const trees = new Trees(treeData, terrain)
    const wind = new WindArrows(terrain.width, terrain.depth, terrain.maxHeight + 18)
    const effects = new FireEffects(terrain)
    const markers = new THREE.Group()
    scene.add(terrain.mesh, trees.group, wind.group, effects.group, markers)
    current = { id: meta.id, terrain, trees, wind, effects, markers }
    frameCamera(terrain)
    updateWind(appState.get())
  }

  function unload() {
    if (!current) return
    const { terrain, trees, wind, effects, markers } = current
    scene.remove(terrain.mesh, trees.group, wind.group, effects.group, markers)
    terrain.dispose()
    trees.dispose()
    wind.dispose()
    effects.dispose()
    clearMarkers(markers)
    current = null
  }

  function frameCamera(t: Terrain) {
    const w = t.width
    const d = t.depth
    const midH = (t.minHeight + t.maxHeight) / 2
    controls.target.set(w / 2, midH, d / 2)
    camera.position.set(w * 0.5, t.maxHeight + Math.max(w, d) * 0.75, d * 1.35)
    controls.maxDistance = Math.max(w, d) * 3
    const span = Math.max(w, d)
    sun.position.set(w * 0.2, t.maxHeight + span, -d * 0.3)
    sun.target.position.set(w / 2, midH, d / 2)
    const cam = sun.shadow.camera
    cam.left = cam.bottom = -span * 0.75
    cam.right = cam.top = span * 0.75
    cam.far = span * 3
    cam.updateProjectionMatrix()
    controls.update()
  }

  function addMarker(x: number, y: number) {
    if (!current) return
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(2.2, 3, 32),
      new THREE.MeshBasicMaterial({ color: '#ff3b1f', side: THREE.DoubleSide, depthTest: false, transparent: true }),
    )
    ring.rotation.x = -Math.PI / 2
    ring.position.set(x, current.terrain.heightAt(x, y) + 0.4, y)
    ring.renderOrder = 2
    current.markers.add(ring)
  }

  function clearMarkers(group: THREE.Group) {
    for (const m of group.children as THREE.Mesh[]) {
      m.geometry.dispose()
      ;(m.material as THREE.Material).dispose()
    }
    group.clear()
  }

  function updateWind(s: AppState) {
    if (!current) return
    current.wind.update(windAt(s.params, s.frame?.t ?? 0), viewOptions.get().windArrows)
  }

  // Ignition click: raycast on the terrain, world (x, _, z) -> sim (x, y).
  const raycaster = new THREE.Raycaster()
  const down = new THREE.Vector2()
  renderer.domElement.addEventListener('pointerdown', (e) => down.set(e.clientX, e.clientY))
  renderer.domElement.addEventListener('pointerup', (e) => {
    if (e.button !== 0 || !current) return
    if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > CLICK_TOLERANCE) return
    const rect = renderer.domElement.getBoundingClientRect()
    const ndc = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1,
    )
    raycaster.setFromCamera(ndc, camera)
    const hit = raycaster.intersectObject(current.terrain.mesh)[0]
    if (!hit) return
    const { x, z } = hit.point
    addMarker(x, z)
    const s = appState.get()
    if (s.sessionId && s.simState !== 'idle') {
      sim.ignite(x, z)
    } else {
      // Idle: start the session and ignite once it exists.
      pending.push([x, z])
      if (pending.length === 1) sim.start().catch((err) => appState.set({ error: String(err) }))
    }
  })

  appState.subscribe((s, prev) => {
    if (s.scene && s.scene.id !== prev.scene?.id) {
      pending = []
      load(s.scene).catch((e) => appState.set({ error: `no se pudo cargar la escena: ${e.message}` }))
    }
    if (!current) return
    if (s.sessionId !== prev.sessionId) {
      // New session (start or reset): clean burn state, keep clicks made while idle.
      current.terrain.resetBurn()
      current.trees.reset()
      current.effects.clear()
      if (s.sessionId) {
        if (!pending.length) clearMarkers(current.markers)
        for (const [x, y] of pending) sim.ignite(x, y)
        pending = []
      } else {
        clearMarkers(current.markers)
      }
    }
    if (s.frame && s.frame !== prev.frame) {
      const opts = viewOptions.get()
      current.terrain.update(s.frame, opts.isochrones ? opts.isoInterval : null)
      current.trees.update(s.frame)
      current.effects.update(s.frame)
    }
    if (s.params !== prev.params || s.frame !== prev.frame) updateWind(s)
  })

  viewOptions.subscribe((o, prev) => {
    updateWind(appState.get())
    if (!o.effects && prev.effects) current?.effects.clear()
    const frame = appState.get().frame
    if (current && frame && (o.isochrones !== prev.isochrones || o.isoInterval !== prev.isoInterval)) {
      current.terrain.update(frame, o.isochrones ? o.isoInterval : null)
    }
  })

  const resize = () => {
    const { clientWidth: w, clientHeight: h } = container
    renderer.setSize(w, h)
    camera.aspect = w / Math.max(h, 1)
    camera.updateProjectionMatrix()
  }
  new ResizeObserver(resize).observe(container)
  resize()

  const clock = new THREE.Clock()
  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.1)
    controls.update()
    if (current) {
      current.trees.animate(clock.elapsedTime)
      const s = appState.get()
      if (viewOptions.get().effects && s.simState !== 'idle') {
        current.effects.animate(s.simState === 'running' ? dt : dt * 0.3, windAt(s.params, s.frame?.t ?? 0))
      }
    }
    renderer.render(scene, camera)
  })
}
