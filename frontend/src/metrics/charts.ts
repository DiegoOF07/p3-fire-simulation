import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import type { Metrics } from '../core/protocol'
import { appState } from '../core/state'

const TEXT = '#c3c2b7'
const GRID = '#383835'
const WIDTH = 380
const HEIGHT = 170

interface ChartDef {
  title: string
  unit: string
  color: string
  floor: number // y axis always includes this value
  minSpan: number // smallest y range shown, avoids a flat squashed line
  value: (m: Metrics) => number
}

const CHARTS: ChartDef[] = [
  { title: 'Área quemada', unit: 'm²', color: '#3987e5', floor: 0, minSpan: 100, value: (m) => m.burned_area },
  { title: 'Temperatura máxima', unit: 'K', color: '#d95926', floor: 300, minSpan: 200, value: (m) => m.T_max },
]

const precise = new Intl.NumberFormat('es', { maximumFractionDigits: 1 })
const short = (v: number) => (Math.abs(v) >= 10_000 ? `${precise.format(v / 1000)} k` : precise.format(v))

const NICE = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]

function niceCeil(v: number): number {
  const p = 10 ** Math.floor(Math.log10(v))
  return (NICE.find((m) => m * p >= v) ?? 10) * p
}

function el(tag: string, className: string, text = ''): HTMLElement {
  const node = document.createElement(tag)
  node.className = className
  node.textContent = text
  return node
}

const axis = (values: uPlot.Axis['values'], extra: uPlot.Axis = {}): uPlot.Axis => ({
  stroke: TEXT,
  values,
  grid: { stroke: GRID, width: 1 },
  ticks: { show: false },
  font: '11px system-ui, sans-serif',
  ...extra,
})

function makeChart(def: ChartDef, container: HTMLElement): { plot: uPlot; show: (u: uPlot, i: number | null) => void } {
  const card = el('div', 'metric')
  const head = el('div', 'metric-head')
  const key = el('span', 'metric-key')
  key.style.background = def.color
  const valueEl = el('span', 'metric-value', '–')
  head.append(key, el('span', 'metric-title', def.title), valueEl)
  card.append(head)
  container.append(card)

  const plot = new uPlot(
    {
      width: WIDTH,
      height: HEIGHT,
      legend: { show: false },
      cursor: { drag: { x: false, y: false }, points: { size: 8 } },
      scales: {
        x: { time: false, range: (_u, _min, max) => [0, Math.max(10, niceCeil(max || 10))] },
        y: {
          range: (_u, min, max) => {
            const lo = Math.min(def.floor, min ?? def.floor)
            const hi = Math.max((max ?? lo) * 1.1, lo + def.minSpan)
            return [lo, lo + niceCeil(hi - lo)]
          },
        },
      },
      series: [{}, { stroke: def.color, width: 2, points: { show: false } }],
      axes: [
        axis((_u, ticks) => ticks.map((t) => `${precise.format(t)} s`)),
        axis((_u, ticks) => ticks.map(short), { size: 48 }),
      ],
      hooks: { setCursor: [(u) => show(u, u.cursor.idx ?? null)] },
    },
    [[], []],
    card,
  )

  // Hovered point, or the latest one.
  function show(u: uPlot, idx: number | null) {
    const [xs, ys] = u.data as [number[], number[]]
    const i = idx ?? ys.length - 1
    valueEl.textContent = i < 0 ? '–' : `${precise.format(ys[i])} ${def.unit}` + (idx == null ? '' : ` · ${precise.format(xs[i])} s`)
  }
  return { plot, show }
}

/** Live metric charts; history resets on every new session. */
export function mountCharts(container: HTMLElement): void {
  container.classList.add('metrics-panel')
  const t: number[] = []
  const series = CHARTS.map(() => [] as number[])
  const charts = CHARTS.map((def) => makeChart(def, container))

  appState.subscribe((s, prev) => {
    if (s.sessionId !== prev.sessionId) {
      t.length = 0
      series.forEach((ys) => (ys.length = 0))
    } else if (!s.metrics || s.metrics === prev.metrics) {
      return
    } else {
      t.push(s.metrics.t)
      CHARTS.forEach((def, i) => series[i].push(def.value(s.metrics!)))
    }
    charts.forEach(({ plot, show }, i) => {
      plot.setData([t, series[i]])
      if (plot.cursor.idx == null) show(plot, null)
    })
  })
}
