import GUI, { type Controller } from 'lil-gui'
import { getPresets } from '../core/api'
import { SPEEDS, type ParamSpec, type PresetInfo, type Speed } from '../core/protocol'
import type { SimController } from '../core/sim'
import { appState, type AppState } from '../core/state'
import { viewOptions } from '../scene/options'

const WIND_MODES = { Despreciable: 0, Constante: 1, Variable: 2 }
const STATE_LABEL = { idle: 'listo', running: 'corriendo', paused: 'en pausa', finished: 'terminado' }

// Folder per parameter; unknown names land in "Otros" so new solver params still show up.
const GROUPS: [string, (name: string) => boolean, boolean][] = [
  ['Ignición', (n) => n === 'ignition_T', true],
  ['Viento', (n) => n.startsWith('wind_'), true],
  ['Combustible', (n) => ['ground_fuel', 'tree_fuel', 'moisture'].includes(n), true],
  ['Terreno', (n) => n === 'slope_factor', true],
  ['Física avanzada', (n) => ['kappa', 'A', 'B', 'C', 'eps', 'T_inf'].includes(n), false],
]
const LABELS: Record<string, string> = {
  ignition_T: 'Temperatura de ignición',
  wind_mode: 'Modo',
  wind_speed: 'Velocidad',
  wind_dir: 'Dirección (hacia)',
  wind_gust: 'Ráfagas',
  wind_period: 'Período ráfagas',
  wind_swing: 'Oscilación dirección',
  ground_fuel: 'Combustible del suelo',
  tree_fuel: 'Combustible de árboles',
  moisture: 'Humedad',
  slope_factor: 'Efecto de la pendiente',
  kappa: 'κ difusión',
  A: 'A calor liberado',
  B: 'B activación',
  C: 'C enfriamiento',
  eps: 'ε consumo',
  T_inf: 'T ambiente',
}
// Wind params that only matter for some modes.
const WIND_NEEDS: Record<string, number> = { wind_speed: 1, wind_dir: 1, wind_gust: 2, wind_period: 2, wind_swing: 2 }

// Firebreak width variants (firebreak_8, …) are for experiments; keep the menu short.
const isVariant = (p: PresetInfo) => /_\d+$/.test(p.id)

export function mountPanel(container: HTMLElement, sim: SimController): void {
  const gui = new GUI({ container, title: 'Simulador de incendio', width: 300 })
  const paramCtrls = new Map<string, Controller>()
  const values: Record<string, number> = {}

  // Simulation controls.
  const actions = {
    estado: STATE_LABEL.idle,
    principal: () => {
      const s = appState.get().simState
      if (s === 'idle') sim.start()
      else if (s === 'running') sim.pause()
      else if (s === 'paused') sim.resume()
      else sim.reset()
    },
    reiniciar: () => sim.reset(),
    velocidad: appState.get().speed as Speed,
    exportar: () => sim.exportCsv(),
  }
  const simFolder = gui.addFolder('Simulación')
  const stateCtrl = simFolder.add(actions, 'estado').name('Estado').disable()
  const mainBtn = simFolder.add(actions, 'principal').name('▶ Iniciar')
  const resetBtn = simFolder.add(actions, 'reiniciar').name('↺ Reiniciar')
  const speedCtrl = simFolder
    .add(actions, 'velocidad', Object.fromEntries(SPEEDS.map((v) => [`×${v}`, v])))
    .name('Velocidad')
    .onChange((v: Speed) => sim.setSpeed(Number(v) as Speed))
  const exportBtn = simFolder.add(actions, 'exportar').name('⤓ Exportar CSV')
  const hint = document.createElement('div')
  hint.className = 'panel-hint'
  hint.textContent = 'Clic sobre el terreno para encender un foco. Arrastra para rotar.'
  simFolder.$children.appendChild(hint)

  // Scene selection.
  const sceneOpts = { preset: 'flat', density: 1, seed: 0, generar: () => loadScene(), azar: () => {
    sceneOpts.seed = Math.floor(Math.random() * 1000)
    seedCtrl.updateDisplay()
    loadScene()
  } }
  const sceneFolder = gui.addFolder('Escena')
  let presetCtrl = sceneFolder.add(sceneOpts, 'preset', { Plano: 'flat' }).name('Escenario')
  const presetInfo = document.createElement('div')
  presetInfo.className = 'panel-hint'
  sceneFolder.$children.appendChild(presetInfo)
  sceneFolder.add(sceneOpts, 'density', 0, 2, 0.05).name('Densidad de árboles')
  const seedCtrl = sceneFolder.add(sceneOpts, 'seed', 0, 999, 1).name('Semilla')
  sceneFolder.add(sceneOpts, 'generar').name('Generar escena')
  sceneFolder.add(sceneOpts, 'azar').name('Semilla al azar')
  let presets: PresetInfo[] = []

  function loadScene() {
    const { preset, density, seed } = sceneOpts
    sim.loadScene({ preset, density, seed }).catch((e) => appState.set({ error: String(e) }))
  }

  function showPresetInfo() {
    presetInfo.textContent = presets.find((p) => p.id === sceneOpts.preset)?.description ?? ''
  }
  getPresets()
    .then((list) => {
      presets = list
      const visible = list.filter((p) => !isVariant(p))
      // options() replaces the controller, so the handler goes on the new one.
      presetCtrl = presetCtrl.options(Object.fromEntries(visible.map((p) => [p.name, p.id]))).name('Escenario')
      presetInfo.remove()
      presetCtrl.domElement.after(presetInfo)
      presetCtrl.onChange(() => {
        showPresetInfo()
        loadScene()
      })
      const req = appState.get().sceneRequest
      if (req) Object.assign(sceneOpts, req)
      gui.controllersRecursive().forEach((c) => c.updateDisplay())
      showPresetInfo()
    })
    .catch((e) => appState.set({ error: `no se pudieron leer las escenas: ${e.message}` }))

  // Physical parameters, built from /api/params.
  function buildParams(specs: ParamSpec[]) {
    for (const c of paramCtrls.values()) c.destroy()
    paramCtrls.clear()
    for (const f of gui.folders.filter((f) => f._title !== 'Simulación' && f._title !== 'Escena' && f._title !== 'Vista')) {
      f.destroy()
    }
    const folders = new Map<string, GUI>()
    const folderFor = (name: string) => {
      const g = GROUPS.find(([, match]) => match(name))
      const title = g?.[0] ?? 'Otros'
      if (!folders.has(title)) {
        const f = gui.addFolder(title)
        if (g && !g[2]) f.close()
        folders.set(title, f)
      }
      return folders.get(title)!
    }
    // Keep group order stable regardless of spec order.
    const ordered = [...specs].sort((a, b) => groupIndex(a.name) - groupIndex(b.name))
    const params = appState.get().params
    for (const spec of ordered) {
      values[spec.name] = params[spec.name] ?? spec.default
      const folder = folderFor(spec.name)
      const label = labelFor(spec)
      const ctrl =
        spec.name === 'wind_mode'
          ? folder.add(values, spec.name, WIND_MODES)
          : folder.add(values, spec.name, spec.min, spec.max, spec.step ?? niceStep(spec))
      ctrl.name(label).onFinishChange((v: number) => {
        if (!sim.setParam(spec.name, Number(v))) {
          values[spec.name] = appState.get().params[spec.name]
          ctrl.updateDisplay()
        }
        refreshEnabled(appState.get())
      })
      if (!spec.live) ctrl.domElement.title = 'Solo se puede cambiar antes de iniciar'
      paramCtrls.set(spec.name, ctrl)
    }
    // Param folders are appended last; keep "Vista" at the bottom.
    viewFolder.domElement.parentElement?.appendChild(viewFolder.domElement)
  }

  // View toggles (local only).
  const view = { ...viewOptions.get() }
  const viewFolder: GUI = gui.addFolder('Vista')
  viewFolder.add(view, 'isochrones').name('Isócronas').onChange((v: boolean) => viewOptions.set({ isochrones: v }))
  viewFolder.add(view, 'isoInterval', 5, 60, 5).name('Cada (s)').onChange((v: number) => viewOptions.set({ isoInterval: v }))
  viewFolder.add(view, 'effects').name('Brasas y humo').onChange((v: boolean) => viewOptions.set({ effects: v }))
  viewFolder.add(view, 'windArrows').name('Flechas de viento').onChange((v: boolean) => viewOptions.set({ windArrows: v }))
  viewFolder.close()

  function refreshEnabled(s: AppState) {
    const mode = Math.round(s.params.wind_mode ?? 0)
    for (const [name, ctrl] of paramCtrls) {
      const needs = WIND_NEEDS[name]
      ctrl.enable(sim.canEdit(name) && (needs === undefined || mode >= needs))
    }
  }

  function refreshButtons(s: AppState) {
    actions.estado = STATE_LABEL[s.simState]
    stateCtrl.updateDisplay()
    mainBtn.name({ idle: '▶ Iniciar', running: '❚❚ Pausar', paused: '▶ Reanudar', finished: '↺ Nueva corrida' }[s.simState])
    mainBtn.enable(!!s.scene)
    resetBtn.enable(!!s.sessionId)
    exportBtn.enable(!!s.sessionId)
    if (actions.velocidad !== s.speed) {
      actions.velocidad = s.speed
      speedCtrl.updateDisplay()
    }
  }

  appState.subscribe((s, prev) => {
    if (s.paramSpecs !== prev.paramSpecs) buildParams(s.paramSpecs)
    if (s.params !== prev.params) {
      for (const [name, ctrl] of paramCtrls) {
        if (values[name] !== s.params[name] && s.params[name] !== undefined) {
          values[name] = s.params[name]
          ctrl.updateDisplay()
        }
      }
    }
    if (s.simState !== prev.simState || s.params !== prev.params || s.paramSpecs !== prev.paramSpecs) refreshEnabled(s)
    if (s.simState !== prev.simState || s.sessionId !== prev.sessionId || s.speed !== prev.speed || s.scene !== prev.scene) {
      refreshButtons(s)
    }
  })

  const s = appState.get()
  if (s.paramSpecs.length) buildParams(s.paramSpecs)
  refreshEnabled(s)
  refreshButtons(s)
}

function groupIndex(name: string): number {
  const i = GROUPS.findIndex(([, match]) => match(name))
  return i < 0 ? GROUPS.length : i
}

function labelFor(spec: ParamSpec): string {
  const base = LABELS[spec.name] ?? spec.label ?? spec.name
  return spec.unit && spec.name !== 'wind_mode' ? `${base} (${spec.unit})` : base
}

function niceStep(spec: ParamSpec): number {
  const span = spec.max - spec.min
  return span >= 100 ? 1 : span >= 10 ? 0.1 : 0.01
}
