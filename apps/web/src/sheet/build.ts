import type { Chord, LyricLine, Section, Song } from '../types'

/** ประกอบ Chord Sheet (คอร์ดบน เนื้อร้องล่าง) จาก song.chords + song.lyrics + song.sections — ฟังก์ชัน pure ทดสอบได้ */

export interface SheetChord { symbol: string; start: number; bass: string | null }
export interface Slot { text: string; start: number; end: number; chords: SheetChord[] }
export interface Row {
  kind: 'lyric' | 'instr'
  start: number
  end: number
  slots: Slot[] // kind = lyric
  chords: SheetChord[] // kind = instr
  lineId?: string
}
export interface SheetSection { section: Section | null; rows: Row[] }

const PRE = 0.25 // คอร์ดที่เริ่มก่อนบรรทัดเนื้อเล็กน้อยยังนับเป็นของบรรทัดนั้น
const TAIL = 1.0 // คอร์ดที่เริ่มหลังบรรทัดจบไม่เกินนี้ยังนับเป็นของบรรทัดนั้น (ท้ายวลี)
const INSTR_PER_ROW = 8

const toSheet = (c: Chord): SheetChord => ({ symbol: c.symbol, start: c.start, bass: c.bass })

export function buildSheet(song: Pick<Song, 'chords' | 'lyrics' | 'sections'>, opts: { dedupe?: boolean } = {}): SheetSection[] {
  let chords = (song.chords ?? []).filter((c) => c.symbol !== 'N').sort((a, b) => a.start - b.start)
  if (opts.dedupe) chords = chords.filter((c, i) => i === 0 || c.symbol !== chords[i - 1].symbol) // "ซ่อนคอร์ดซ้ำ"
  const lines: LyricLine[] = [...(song.lyrics?.lines ?? [])].sort((a, b) => a.start - b.start)
  const rows: Row[] = []
  const used = new Set<number>()

  lines.forEach((line, li) => {
    const next = lines[li + 1]
    const hi = Math.min(line.end + TAIL, next ? next.start - PRE : Infinity)
    const slots: Slot[] = line.words.map((w) => ({ text: w.text, start: w.start, end: w.end, chords: [] }))
    chords.forEach((c, ci) => {
      if (used.has(ci) || c.start < line.start - PRE || c.start >= hi || slots.length === 0) return
      let k = slots.findIndex((s) => s.end > c.start + 0.05)
      if (k < 0) k = slots.length - 1 // เลยท้ายบรรทัด → ปลายบรรทัด
      slots[k].chords.push(toSheet(c))
      used.add(ci)
    })
    rows.push({ kind: 'lyric', start: line.start, end: line.end, slots, chords: [], lineId: line.id })
  })

  // คอร์ดที่ไม่ตกในบรรทัดเนื้อใดเลย = ช่วงบรรเลง → จัดเป็นแถวละไม่เกิน INSTR_PER_ROW คอร์ด (ตัดแถวเมื่อมีบรรทัดเนื้อคั่น)
  let run: SheetChord[] = []
  const flush = () => {
    for (let i = 0; i < run.length; i += INSTR_PER_ROW) {
      const part = run.slice(i, i + INSTR_PER_ROW)
      rows.push({ kind: 'instr', start: part[0].start, end: part[part.length - 1].start, slots: [], chords: part })
    }
    run = []
  }
  chords.forEach((c, ci) => {
    if (used.has(ci)) {
      flush()
      return
    }
    // คั่นด้วยบรรทัดเนื้อที่เริ่มหลังคอร์ดล่าสุดใน run และก่อนคอร์ดนี้
    const last = run[run.length - 1]
    if (last && lines.some((l) => l.start > last.start && l.start <= c.start)) flush()
    run.push(toSheet(c))
  })
  flush()
  rows.sort((a, b) => a.start - b.start)

  // จัดเข้าท่อนตามเวลาเริ่มของแถว
  const secs = [...(song.sections ?? [])].sort((a, b) => a.start - b.start)
  const out: SheetSection[] = []
  for (const row of rows) {
    const sec = secs.filter((s) => row.start >= s.start - 0.01).pop() ?? null
    const inSec = sec && row.start < sec.end + 0.5 ? sec : sec // แถวหลังท่อนสุดท้ายยังอยู่ท่อนสุดท้าย
    const cur = out[out.length - 1]
    if (cur && (cur.section?.id ?? null) === (inSec?.id ?? null)) cur.rows.push(row)
    else out.push({ section: inSec, rows: [row] })
  }
  return out
}

/** แถวที่กำลังเล่นอยู่ ณ เวลา t (ไฮไลต์แบบคาราโอเกะ) */
export function activeRow(sheet: SheetSection[], t: number): { section: number; row: number } | null {
  let best: { section: number; row: number } | null = null
  sheet.forEach((s, si) => s.rows.forEach((r, ri) => { if (r.start <= t + 0.05) best = { section: si, row: ri } }))
  return best
}
