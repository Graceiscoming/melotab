import type { Beat, Note } from '../types'

/** ช่องต่อ beat ของการ quantize/snap (4 = 1/16 ใน 4/4) — ต้องตรงกับ QUANT_DIV ของ backend */
export const QUANT_DIV = 4

/** เวลา (วินาที) → ตำแหน่งในหน่วย beat (นับจาก beat แรก = 0) โดย interpolate ตาม beat grid จริง */
export function timeToBeat(beats: Beat[], t: number): number {
  if (beats.length < 2) return t
  const first = beats[0].time
  const last = beats[beats.length - 1].time
  if (t <= first) return (t - first) / (beats[1].time - first)
  if (t >= last) return beats.length - 1 + (t - last) / (last - beats[beats.length - 2].time)
  let lo = 0
  let hi = beats.length - 1
  while (hi - lo > 1) {
    const m = (lo + hi) >> 1
    if (beats[m].time <= t) lo = m
    else hi = m
  }
  return lo + (t - beats[lo].time) / (beats[hi].time - beats[lo].time)
}

export function beatToTime(beats: Beat[], b: number): number {
  if (beats.length < 2) return b
  const n = beats.length
  if (b <= 0) return beats[0].time + b * (beats[1].time - beats[0].time)
  if (b >= n - 1) return beats[n - 1].time + (b - (n - 1)) * (beats[n - 1].time - beats[n - 2].time)
  const i = Math.floor(b)
  return beats[i].time + (b - i) * (beats[i + 1].time - beats[i].time)
}

/** ปัดเวลาเข้ากริด 1/QUANT_DIV beat ถ้าไม่มี beat grid คืนค่าเดิม */
export function snapTime(beats: Beat[], t: number, div = QUANT_DIV): number {
  if (beats.length < 2) return t
  return beatToTime(beats, Math.round(timeToBeat(beats, t) * div) / div)
}

const r3 = (x: number) => Math.round(x * 1000) / 1000

/** คำนวณ start_beat / dur_beats และค่า quantized ใหม่ให้โน้ต (เหมือน _beat_positions ใน backend) */
export function withBeatPositions(notes: Note[], beats: Beat[]): Note[] {
  if (beats.length < 2) return notes
  return notes.map((n) => {
    const s = timeToBeat(beats, n.start)
    const e = timeToBeat(beats, n.end)
    const qs = Math.round(s * QUANT_DIV) / QUANT_DIV
    const qe = Math.max(qs + 1 / QUANT_DIV, Math.round(e * QUANT_DIV) / QUANT_DIV)
    return { ...n, start_beat: r3(s), dur_beats: r3(e - s), start_beat_q: r3(qs), dur_beats_q: r3(qe - qs) }
  })
}
