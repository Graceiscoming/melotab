import { describe, expect, it } from 'vitest'
import type { Beat, TabEvent } from '../types'
import { barsFromBeats, layoutTab, LAYOUT, timeToPos } from './layout'

const beats: Beat[] = Array.from({ length: 17 }, (_, i) => ({ time: i * 0.5, bar: Math.floor(i / 4) + 1, beat: (i % 4) + 1 }))   // 4/4 120 BPM 4 ห้อง

const ev = (id: string, startBeat: number, extra: Partial<TabEvent> = {}): TabEvent => ({
  id, note_id: id, pitch: 60, string: 2, fret: 1, start: startBeat * 0.5, end: startBeat * 0.5 + 0.4, start_beat: startBeat, dur_beats: 0.8,
  techniques: {}, bend: null, finger: null, locked: false, difficulty: 0, warnings: [], ...extra,
})

describe('barsFromBeats', () => {
  it('แบ่งห้องที่ downbeat', () => {
    const bars = barsFromBeats(beats, 16)
    expect(bars.slice(0, 4).map((b) => [b.startBeat, b.beats])).toEqual([[0, 4], [4, 4], [8, 4], [12, 4]])
  })
  it('มีห้อง pickup ถ้า downbeat แรกไม่ใช่ beat แรก', () => {
    const b = beats.map((x, i) => ({ ...x, beat: ((i + 2) % 4) + 1 }))   // downbeat แรกที่ index 2
    const bars = barsFromBeats(b, 16)
    expect(bars[0]).toEqual({ startBeat: 0, beats: 2 })
    expect(bars[1].startBeat).toBe(2)
  })
  it('ไม่มี beat grid → 4/4 สังเคราะห์', () => expect(barsFromBeats([], 8).map((b) => b.beats)).toEqual([4, 4]))
})

describe('layoutTab', () => {
  it('วางโน้ตตามตำแหน่ง beat และเรียงซ้ายไปขวา', () => {
    const l = layoutTab([ev('a', 0), ev('b', 1), ev('c', 4.5)], beats, 2000, 8)
    const pos = (id: string) => l.eventPos.get(id)!
    expect(pos('b').x - pos('a').x).toBeCloseTo(LAYOUT.beatW)
    expect(pos('c').x).toBeGreaterThan(pos('b').x)
    expect(l.systems.length).toBe(1)
  })
  it('โน้ตแน่นเกินไม่ซ้อนกัน (ระยะห่างขั้นต่ำ)', () => {
    const l = layoutTab([ev('a', 0), ev('b', 0.25), ev('c', 0.5)], beats, 2000, 8)
    const xs = ['a', 'b', 'c'].map((id) => l.eventPos.get(id)!.x)
    expect(xs[1] - xs[0]).toBeGreaterThanOrEqual(LAYOUT.minGap)
    expect(xs[2] - xs[1]).toBeGreaterThanOrEqual(LAYOUT.minGap)
  })
  it('ตัดบรรทัดตามความกว้าง และ event อยู่บรรทัดที่ถูก', () => {
    const l = layoutTab([ev('a', 0), ev('z', 14)], beats, 400, 8)
    expect(l.systems.length).toBeGreaterThan(1)
    expect(l.eventPos.get('a')!.system).toBe(0)
    expect(l.eventPos.get('z')!.system).toBeGreaterThan(l.eventPos.get('a')!.system)   // ยังมีห้องว่างต่อท้ายตามความยาว beat grid
  })
  it('event ที่เล่นไม่ได้ (fret = null) ไม่ถูกวาง', () => {
    const l = layoutTab([ev('a', 0), ev('x', 1, { fret: null, string: null })], beats, 2000, 8)
    expect(l.eventPos.has('x')).toBe(false)
  })
  it('timeToPos หาตำแหน่ง playhead ในห้องที่ถูกต้อง', () => {
    const l = layoutTab([ev('a', 0)], beats, 2000, 8)
    const p0 = timeToPos(l, beats, 0)!
    const p1 = timeToPos(l, beats, 1.0)!    // beat 2
    expect(p1.x).toBeGreaterThan(p0.x)
    expect(timeToPos({ ...l, systems: [] }, beats, 1)).toBeNull()
  })
})
