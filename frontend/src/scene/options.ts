import { createStore } from '../core/state'

// View-only toggles shared by the scene and the panel; nothing here reaches the server.
export interface ViewOptions {
  isochrones: boolean
  isoInterval: number // s between isochrone lines
  effects: boolean // embers and smoke
  windArrows: boolean
}

export const viewOptions = createStore<ViewOptions>({
  isochrones: false,
  isoInterval: 20,
  effects: true,
  windArrows: true,
})
