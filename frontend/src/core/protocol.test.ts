import { describe, expect, it } from 'vitest'
import { cellState, decodeFrame, HEADER_SIZE } from './protocol'

// Shared with backend/tests/test_api_protocol.py.
const GOLDEN_HEX = '07000000' + '0000c03f' + '0300' + '0200' + '01000000' + '000102030405' + 'fffefdfcfbfa'

function fromHex(hex: string): ArrayBuffer {
  const bytes = new Uint8Array(hex.length / 2)
  for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.slice(2 * i, 2 * i + 2), 16)
  return bytes.buffer
}

describe('decodeFrame', () => {
  it('decodes the golden frame packed by the backend', () => {
    const f = decodeFrame(fromHex(GOLDEN_HEX))
    expect([f.frame, f.t, f.nx, f.ny, f.version]).toEqual([7, 1.5, 3, 2, 1])
    expect([...f.T]).toEqual([0, 1, 2, 3, 4, 5])
    expect([...f.beta]).toEqual([255, 254, 253, 252, 251, 250])
  })

  it('rejects truncated buffers', () => {
    expect(() => decodeFrame(fromHex(GOLDEN_HEX).slice(0, -1))).toThrow()
    expect(() => decodeFrame(new ArrayBuffer(HEADER_SIZE - 1))).toThrow()
  })

  it('rejects unknown versions', () => {
    const buf = fromHex(GOLDEN_HEX)
    new DataView(buf).setUint8(12, 99)
    expect(() => decodeFrame(buf)).toThrow(/version/)
  })
})

describe('cellState', () => {
  it('classifies by thresholds', () => {
    expect(cellState(200, 200)).toBe('burning')
    expect(cellState(0, 10)).toBe('burnt')
    expect(cellState(0, 255)).toBe('unburnt')
  })
})
