import type { Beat, TabEvent } from '../types'
import { timeToBeat } from '../theory/rhythm'

/** จัดวางแทปเป็นห้อง (bar) แล้วเรียงเป็นบรรทัด (system) — ฟังก์ชัน pure ทดสอบได้ ไม่แตะ DOM */

export interface BarLayout {
  index: number
  startBeat: number // beat (นับจาก beat แรก = 0) ที่ห้องนี้เริ่ม
  beats: number // จำนวน beat ในห้อง
  x: number // ตำแหน่งซ้ายของห้องภายในบรรทัด
  width: number
  events: { id: string; x: number }[] // x สัมพันธ์กับซ้ายของ "บรรทัด"
}
export interface SystemLayout { index: number; bars: BarLayout[]; width: number }
export interface TabLayout {
  systems: SystemLayout[]
  /** ตำแหน่ง x (ภายในบรรทัด) ของ event ทุกตัว + บรรทัดที่อยู่ */
  eventPos: Map<string, { system: number; x: number }>
  bars: { startBeat: number; beats: number }[]
}

export const LAYOUT = { beatW: 56, minGap: 17, barPad: 14, leftMargin: 34, barLine: 1 }

/** แบ่งห้องจาก beat grid (beat = 1 คือ downbeat) ถ้าไม่มี grid ใช้ 4/4 สังเคราะห์ */
export function barsFromBeats(beats: Beat[], totalBeats: number): { startBeat: number; beats: number }[] {
  const starts: number[] = []
  beats.forEach((b, i) => { if (b.beat === 1) starts.push(i) })
  if (starts.length === 0) {
    const out = []
    for (let s = 0; s < Math.max(4, Math.ceil(totalBeats)); s += 4) out.push({ startBeat: s, beats: 4 })
    return out
  }
  const bars: { startBeat: number; beats: number }[] = []
  if (starts[0] > 0) bars.push({ startBeat: 0, beats: starts[0] }) // ห้อง pickup ก่อน downbeat แรก
  starts.forEach((s, i) => {
    const next = i + 1 < starts.length ? starts[i + 1] : Math.max(s + 4, Math.ceil(totalBeats))
    bars.push({ startBeat: s, beats: Math.max(1, next - s) })
  })
  return bars
}

const barIndexOf = (bars: { startBeat: number; beats: number }[], beat: number): number => {
  if (beat < bars[0].startBeat) return 0
  let lo = 0
  let hi = bars.length - 1
  while (lo < hi) {
    const m = (lo + hi + 1) >> 1
    if (bars[m].startBeat <= beat) lo = m
    else hi = m - 1
  }
  return lo
}

/** beat ของ event สำหรับวางแทป: ใช้ค่า quantized ถ้ามี ไม่งั้นคำนวณจากเวลาจริง */
export function eventBeat(e: TabEvent, beats: Beat[]): number {
  return e.start_beat ?? timeToBeat(beats, e.start)
}

export function layoutTab(events: TabEvent[], beats: Beat[], width: number, duration: number): TabLayout {
  const { beatW, minGap, barPad, leftMargin } = LAYOUT
  const lastBeat = beats.length > 1 ? beats.length : Math.ceil(duration * 2)
  const maxEv = events.reduce((m, e) => Math.max(m, eventBeat(e, beats) + 1), 0)
  const bars = barsFromBeats(beats, Math.max(lastBeat, maxEv))
  const perBar: TabEvent[][] = bars.map(() => [])
  for (const e of [...events].sort((a, b) => eventBeat(a, beats) - eventBeat(b, beats) || a.start - b.start)) {
    if (e.fret === null) continue // เล่นไม่ได้ ไม่วาดเลข (แสดงเตือนที่อื่น)
    perBar[barIndexOf(bars, eventBeat(e, beats))].push(e)
  }
  // คำนวณความกว้างของแต่ละห้อง: ตาม beat แต่ถ้าโน้ตแน่นเกินจะขยายให้ไม่ชนกัน
  const layoutBars = bars.map((b, i) => {
    let prevX = -Infinity
    const evs = perBar[i].map((e) => {
      const nominal = barPad + (eventBeat(e, beats) - b.startBeat) * beatW
      const x = Math.max(nominal, prevX + minGap)
      prevX = x
      return { id: e.id, x }
    })
    const w = Math.max(b.beats * beatW + barPad * 2, (evs.length ? evs[evs.length - 1].x : 0) + barPad * 1.5)
    return { index: i, startBeat: b.startBeat, beats: b.beats, x: 0, width: w, events: evs }
  })
  // ตัดเป็นบรรทัดตามความกว้าง (ห้องเดียวกว้างเกินหน้าจอก็ยังอยู่บรรทัดเดียวของมันเอง)
  const systems: SystemLayout[] = []
  let cur: BarLayout[] = []
  let x = leftMargin
  for (const b of layoutBars) {
    if (cur.length > 0 && x + b.width > width) {
      systems.push({ index: systems.length, bars: cur, width: x })
      cur = []
      x = leftMargin
    }
    cur.push({ ...b, x, events: b.events.map((e) => ({ id: e.id, x: x + e.x })) })
    x += b.width
  }
  if (cur.length) systems.push({ index: systems.length, bars: cur, width: x })
  const eventPos = new Map<string, { system: number; x: number }>()
  systems.forEach((s) => s.bars.forEach((b) => b.events.forEach((e) => eventPos.set(e.id, { system: s.index, x: e.x }))))
  return { systems, eventPos, bars }
}

/** เวลา (วินาที) → ตำแหน่งบนแทป (บรรทัด + x) สำหรับ playhead */
export function timeToPos(layout: TabLayout, beats: Beat[], t: number): { system: number; x: number } | null {
  if (layout.systems.length === 0) return null
  const beat = timeToBeat(beats, t)
  const bi = barIndexOf(layout.bars, beat)
  for (const s of layout.systems) {
    const b = s.bars.find((x) => x.index === bi)
    if (b) {
      const frac = Math.max(0, Math.min(1, (beat - b.startBeat) / b.beats))
      return { system: s.index, x: b.x + LAYOUT.barPad + frac * (b.width - LAYOUT.barPad * 2) }
    }
  }
  return null
}
