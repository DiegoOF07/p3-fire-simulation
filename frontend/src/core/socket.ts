import { decodeFrame, type ClientMsg, type Frame, type ServerMsg } from './protocol'

type Listener<T> = (value: T) => void

export type Connection = 'connecting' | 'open' | 'reconnecting'

export interface ConnectionEvent {
  status: Connection
  reconnected: boolean // true on an open that follows a drop
}

const MIN_DELAY = 500
const MAX_DELAY = 5000

const defaultUrl = () => `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/sim`

/** WebSocket that reconnects with backoff; listeners survive reconnections. */
export class SimSocket {
  private ws!: WebSocket
  private attempt = 0
  private openedOnce = false
  private closed = false
  private frameListeners: Listener<Frame>[] = []
  private msgListeners: Listener<ServerMsg>[] = []
  private connListeners: Listener<ConnectionEvent>[] = []

  constructor(private url = defaultUrl()) {
    this.connect()
  }

  private connect(): void {
    const ws = new WebSocket(this.url)
    ws.binaryType = 'arraybuffer'
    ws.onopen = () => {
      this.attempt = 0
      const reconnected = this.openedOnce
      this.openedOnce = true
      this.emit({ status: 'open', reconnected })
    }
    ws.onmessage = (e) => {
      try {
        if (e.data instanceof ArrayBuffer) {
          const frame = decodeFrame(e.data)
          this.frameListeners.forEach((l) => l(frame))
        } else {
          const msg = JSON.parse(e.data) as ServerMsg
          this.msgListeners.forEach((l) => l(msg))
        }
      } catch (err) {
        console.error('bad message from server', err)
      }
    }
    ws.onclose = () => {
      if (this.closed) return
      this.emit({ status: 'reconnecting', reconnected: false })
      const delay = Math.min(MAX_DELAY, MIN_DELAY * 2 ** this.attempt++)
      setTimeout(() => this.connect(), delay)
    }
    this.ws = ws
  }

  private emit(event: ConnectionEvent): void {
    this.connListeners.forEach((l) => l(event))
  }

  get isOpen(): boolean {
    return this.ws.readyState === WebSocket.OPEN
  }

  whenOpen(): Promise<void> {
    if (this.isOpen) return Promise.resolve()
    return new Promise((resolve) => {
      const listener = (e: ConnectionEvent) => {
        if (e.status !== 'open') return
        this.connListeners = this.connListeners.filter((l) => l !== listener)
        resolve()
      }
      this.connListeners.push(listener)
    })
  }

  /** Returns false when not connected; the message is dropped. */
  send(msg: ClientMsg): boolean {
    if (!this.isOpen) return false
    this.ws.send(JSON.stringify(msg))
    return true
  }

  onFrame(listener: Listener<Frame>): void {
    this.frameListeners.push(listener)
  }

  onMessage(listener: Listener<ServerMsg>): void {
    this.msgListeners.push(listener)
  }

  onConnection(listener: Listener<ConnectionEvent>): void {
    this.connListeners.push(listener)
  }

  close(): void {
    this.closed = true
    this.ws.close()
  }
}
