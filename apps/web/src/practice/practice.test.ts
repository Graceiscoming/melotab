import { describe, expect, it } from 'vitest'
import type { TabEvent } from '../types'
import { detectPitch, hzToMidi } from './pitch'
import { PracticeScorer } from './scorer'

const sine = (hz: number, sr = 44100, n = 4096, harm = false) => {
  const b = new Float32Array(n)
  for (let i = 0; i < n; i++) b[i] = 0.4 * Math.sin((2 * Math.PI * hz * i) / sr) + (harm ? 0.2 * Math.sin((4 * Math.PI * hz * i) / sr) + 0.1 * Math.sin((6 * Math.PI * hz * i) / sr) : 0)
  return b
}
const ev = (id: string, pitch: number, start: number, end: number): TabEvent => ({
  id, note_id: id, pitch, string: 1, fret: 0, start, end, start_beat: 0, dur_beats: 1, techniques: {}, bend: null, finger: null, locked: false, difficulty: 0, warnings: [],
})

describe('detectPitch', () => {
  it('จับ pitch ของกีตาร์ช่วง E2–E6 ได้ภายใน ±5 cents', () => {
    for (const hz of [82.41, 110, 196, 329.63, 659.25, 1318.5]) {
      const r = detectPitch(sine(hz, 44100, 4096, true), 44100)
      expect(r, String(hz)).not.toBeNull()
      expect(Math.abs((hzToMidi(r!.hz) - hzToMidi(hz)) * 100)).toBeLessThan(5)
    }
  })
  it('เงียบ/สัญญาณรบกวน = ไม่มี pitch', () => {
    expect(detectPitch(new Float32Array(4096), 44100)).toBeNull()
    const noise = new Float32Array(4096).map(() => (Math.random() - 0.5) * 0.4)
    const r = detectPitch(noise, 44100)
    expect(r === null || r.clarity < 0.9).toBe(true)
  })
})

describe('PracticeScorer', () => {
  const events = [ev('a', 64, 0, 1), ev('b', 66, 1, 2), ev('c', 67, 2, 3)]
  it('ตัดสินเมื่อโน้ตผ่านไปแล้ว: ถูก/ผิด/คนละ octave', () => {
    const s = new PracticeScorer(events)
    for (let t = 0; t < 3.2; t += 0.05) {
      const want = t < 1 ? 64 : t < 2 ? 66 : 67
      s.update(t, t < 1 ? 64.2 : t < 2 ? 54 : 67 + 12 - 0 * want) // a ถูก (+20 cents), b ผิดมาก, c ตรงแต่สูงไป 1 octave
    }
    expect(s.results.get('a')).toBe('hit')
    expect(s.results.get('b')).toBe('miss')
    expect(s.results.get('c')).toBe('octave')
    expect(s.summary()).toEqual({ hit: 1, miss: 1, octave: 1, total: 3, pct: 33 })
  })
  it('ไม่ตัดสินโน้ตที่ยังไม่ถึง และ seek ข้ามโน้ตก่อนหน้า', () => {
    const s = new PracticeScorer(events)
    s.update(0.5, 64)
    expect(s.results.size).toBe(0)
    s.seek(2.1)
    s.update(2.2, 67)
    s.update(3.1, null)
    expect([...s.results.keys()]).toEqual(['c'])
  })
  it('ไม่มีเสียงเลย = miss', () => {
    const s = new PracticeScorer(events)
    for (let t = 0; t < 3.2; t += 0.05) s.update(t, null)
    expect(s.summary().miss).toBe(3)
  })
})
