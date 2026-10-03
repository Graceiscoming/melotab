import { describe, expect, it } from 'vitest'
import type { Chord, LyricLine } from '../types'
import { activeRow, buildSheet } from './build'

const ch = (symbol: string, start: number, end: number, bass: string | null = null): Chord =>
  ({ symbol, start, end, start_beat: 0, end_beat: 0, root: 0, quality: 'maj', bass, confidence: null })
const line = (id: string, start: number, words: [string, number, number][]): LyricLine => ({
  id, start, end: words[words.length - 1][2], text: words.map((w) => w[0]).join(' '),
  words: words.map(([text, s, e]) => ({ text, start: s, end: e })),
})

const song = {
  chords: [ch('D', 0, 4), ch('A', 4, 6), ch('Bm', 6.2, 8), ch('G', 8, 10), ch('D/F#', 10, 12, 'F#'), ch('E', 20, 22), ch('A', 22, 24)],
  lyrics: {
    language: 'en', source: 'asr' as const,
    lines: [
      line('l1', 4.1, [['alpha', 4.1, 5], ['beta', 5, 6], ['gamma', 6.2, 7.5]]),
      line('l2', 8.1, [['delta', 8.1, 9], ['omega', 9, 11]]),
    ],
  },
  sections: [
    { id: 's1', label: 'Verse 1', start_bar: 1, end_bar: 9, start: 0, end: 15, auto: true },
    { id: 's2', label: 'Chorus', start_bar: 9, end_bar: 20, start: 15, end: 30, auto: true },
  ],
}

describe('buildSheet', () => {
  const sheet = buildSheet(song)

  it('วางคอร์ดบนคำที่กำลังร้องตอนคอร์ดเริ่ม', () => {
    const l1 = sheet[0].rows.find((r) => r.lineId === 'l1')!
    expect(l1.slots.map((s) => s.chords.map((c) => c.symbol))).toEqual([['A'], [], ['Bm']])  // A เริ่ม 4.0 (ก่อนเนื้อเล็กน้อย) → คำแรก, Bm 6.2 → gamma
    const l2 = sheet[0].rows.find((r) => r.lineId === 'l2')!
    expect(l2.slots.map((s) => s.chords.map((c) => c.symbol))).toEqual([['G'], ['D/F#']])
  })

  it('คอร์ดที่เริ่มก่อนเนื้อไม่เกิน 0.25 วินาทีนับเป็นของบรรทัดนั้น แต่ที่ห่างกว่าเป็นแถวบรรเลง', () => {
    const instr = sheet.flatMap((s) => s.rows).filter((r) => r.kind === 'instr')
    expect(instr.map((r) => r.chords.map((c) => c.symbol))).toEqual([['D'], ['E', 'A']])   // D (0–4 s ก่อนเนื้อ) และ E, A ช่วงท้าย
  })

  it('จัดเรียงตามเวลาและแบ่งตามท่อน', () => {
    expect(sheet.map((s) => s.section?.label)).toEqual(['Verse 1', 'Chorus'])
    expect(sheet[0].rows.map((r) => r.start)).toEqual([...sheet[0].rows.map((r) => r.start)].sort((a, b) => a - b))
    expect(sheet[1].rows[0].kind).toBe('instr')
  })

  it('คอร์ดทุกตัว (ที่ไม่ใช่ N) ปรากฏบนใบเนื้อครบ ไม่หายไม่ซ้ำ', () => {
    const shown = sheet.flatMap((s) => s.rows).flatMap((r) => (r.kind === 'lyric' ? r.slots.flatMap((x) => x.chords) : r.chords))
    expect(shown).toHaveLength(song.chords.length)
    expect(new Set(shown.map((c) => c.start)).size).toBe(song.chords.length)
  })

  it('dedupe ซ่อนคอร์ดซ้ำติดกัน', () => {
    const s = buildSheet({ ...song, chords: [ch('D', 0, 2), ch('D', 2, 4), ch('A', 4, 6), ch('A', 6, 8)] }, { dedupe: true })
    const all = s.flatMap((x) => x.rows).flatMap((r) => (r.kind === 'lyric' ? r.slots.flatMap((q) => q.chords) : r.chords))
    expect(all.map((c) => c.symbol)).toEqual(['D', 'A'])
  })

  it('ไม่มีเนื้อ/ท่อน = แถวบรรเลงล้วน (ไม่ล้ม) และไม่มีข้อมูลเลย = ว่าง', () => {
    const only = buildSheet({ chords: song.chords })
    expect(only).toHaveLength(1)
    expect(only[0].section).toBeNull()
    expect(only[0].rows.every((r) => r.kind === 'instr')).toBe(true)
    expect(buildSheet({})).toEqual([])
  })

  it('คอร์ด N ไม่ถูกแสดง', () => {
    const s = buildSheet({ chords: [ch('N', 0, 2), ch('C', 2, 4)] })
    expect(s[0].rows[0].chords.map((c) => c.symbol)).toEqual(['C'])
  })

  it('activeRow หาแถวที่กำลังเล่น', () => {
    const rows = sheet.flatMap((s, si) => s.rows.map((_, ri) => ({ si, ri })))
    expect(rows.length).toBeGreaterThan(3)
    const a = activeRow(sheet, 4.5)!
    expect(sheet[a.section].rows[a.row].lineId).toBe('l1')
    expect(activeRow(sheet, -5)).toBeNull()
  })
})
