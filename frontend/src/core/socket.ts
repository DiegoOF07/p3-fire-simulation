import { decodeFrame, type ClientMsg, type Frame, type ServerMsg } from './protocol'

type Listener<T> = (value: T) => void

export class SimSocket {
  private ws: WebSocket
  private frameListeners: Listener<Frame>[] = []
  private msgListeners: Listener<ServerMsg>[] = []
  readonly ready: Promise<void>

  constructor(url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/sim`) {
    this.ws = new WebSocket(url)
    this.ws.binaryType = 'arraybuffer'
    this.ready = new Promise((resolve, reject) => {
      this.ws.addEventListener('open', () => resolve(), { once: true })
      this.ws.addEventListener('error', () => reject(new Error('websocket error')), { once: true })
    })
    this.ws.addEventListener('message', (e) => {
      if (e.data instanceof ArrayBuffer) {
        const frame = decodeFrame(e.data)
        this.frameListeners.forEach((l) => l(frame))
      } else {
        const msg = JSON.parse(e.data) as ServerMsg
        this.msgListeners.forEach((l) => l(msg))
      }
    })
  }

  send(msg: ClientMsg): void {
    this.ws.send(JSON.stringify(msg))
  }

  onFrame(listener: Listener<Frame>): void {
    this.frameListeners.push(listener)
  }

  onMessage(listener: Listener<ServerMsg>): void {
    this.msgListeners.push(listener)
  }

  close(): void {
    this.ws.close()
  }
}
