import { describe, expect, it } from 'vitest'
import type { Beat, Note } from '../types'
import { beatToTime, snapTime, timeToBeat, withBeatPositions } from './rhythm'

const beats: Beat[] = [0, 1, 2, 2.5, 3].map((time, i) => ({ time, bar: 1, beat: (i % 4) + 1 }))   // tempo เร็วขึ้นท้ายเพลง

describe('rhythm', () => {
  it('timeToBeat interpolate ตามกริดจริง', () => {
    expect(timeToBeat(beats, 0.5)).toBeCloseTo(0.5)
    expect(timeToBeat(beats, 2.25)).toBeCloseTo(2.5)
    expect(timeToBeat(beats, 3.5)).toBeCloseTo(5)                  // นอกช่วงท้าย ใช้ IBI สุดท้าย
    expect(timeToBeat(beats, -1)).toBeCloseTo(-1)
  })
  it('beatToTime เป็นฟังก์ชันผกผัน', () => {
    for (const t of [-0.5, 0, 0.3, 1.7, 2.3, 2.9, 3.4]) expect(beatToTime(beats, timeToBeat(beats, t))).toBeCloseTo(t, 6)
  })
  it('snapTime ปัดเข้า 1/4 beat', () => {
    expect(snapTime(beats, 1.12)).toBeCloseTo(1.0)
    expect(snapTime(beats, 1.13)).toBeCloseTo(1.25)
    expect(snapTime([], 1.13)).toBe(1.13)
  })
  it('withBeatPositions เติม beat และ quantize โดยไม่แตะเวลาจริง', () => {
    const note = { id: 'a', midi: 60, name: '', freq: 0, start: 1.1, end: 1.9, cents_offset: null, confidence: 1, octave_suspect: false, edited: false } as Note
    const [o] = withBeatPositions([note], beats)
    expect(o.start).toBe(1.1)
    expect(o.start_beat_q).toBe(1)
    expect(o.dur_beats_q).toBe(1)
  })
})
