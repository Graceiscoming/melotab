import type { FretPos, Note, TabEvent, TabSettings, Techniques } from '../types'
import { midiToHz, noteName } from '../theory/notes'

/** การแก้แทป (pure) — ผลคือ patch ของโน้ต + ตำแหน่งที่ถูกล็อก เพื่อให้ undo/redo ครอบคลุมทั้งคู่ */

export const TUNINGS: Record<string, number[]> = {
  standard: [40, 45, 50, 55, 59, 64],
  eb: [39, 44, 49, 54, 58, 63],
  drop_d: [38, 45, 50, 55, 59, 64],
  dadgad: [38, 45, 50, 55, 57, 62],
}
export const TUNING_LABEL: Record<string, string> = { standard: 'Standard (E A D G B E)', eb: 'Eb Standard', drop_d: 'Drop D', dadgad: 'DADGAD' }

/** พิทช์ของ (สาย 1..6, ช่อง) ในจูนนิ่ง/capo ที่ตั้งไว้ (สาย 6 = ต่ำสุด) */
export const pitchAt = (s: TabSettings, string: number, fret: number): number => TUNINGS[s.tuning][6 - string] + s.capo + fret
/** ช่องที่เล่น pitch บนสายนั้น (null ถ้านอกคอ) */
export const fretFor = (s: TabSettings, string: number, pitch: number): number | null => {
  const f = pitch - (TUNINGS[s.tuning][6 - string] + s.capo)
  return f >= 0 && f <= s.max_fret ? f : null
}

export interface State { notes: Note[]; locked: Record<string, FretPos>; techniques: Record<string, Techniques> }

const withPitch = (n: Note, midi: number, key: Parameters<typeof noteName>[1]): Note => ({
  ...n, midi, name: noteName(midi, key), freq: Math.round(midiToHz(midi) * 100) / 100,
  confidence: 1, octave_suspect: false, octave_fixed: false, edited: true, cents_offset: null,
})

/** ย้ายสายโดยรักษา pitch เดิม (คำนวณช่องให้) คืน null ถ้าสายนั้นเล่นโน้ตนี้ไม่ได้ */
export function moveString(st: State, ev: TabEvent, dir: 1 | -1, s: TabSettings): State | null {
  if (ev.string === null) return null
  const ns = ev.string + dir // dir = 1 → ลงสายหนา (เลขสายเพิ่ม), -1 → ขึ้นสายบาง
  if (ns < 1 || ns > 6) return null
  const f = fretFor(s, ns, ev.pitch)
  if (f === null) return null
  return { ...st, locked: { ...st.locked, [ev.note_id]: { string: ns, fret: f } } }
}

/** ตั้งช่อง (บนสายเดิม): pitch เปลี่ยนตาม → แก้โน้ตด้วย (โน้ตเดิม = pitch − transpose) */
export function setFret(st: State, ev: TabEvent, fret: number, s: TabSettings, key: Parameters<typeof noteName>[1]): State | null {
  if (ev.string === null || fret < 0 || fret > s.max_fret) return null
  const pitch = pitchAt(s, ev.string, fret)
  const midi = pitch - s.transpose
  if (midi < 21 || midi > 108) return null
  return {
    ...st,
    notes: st.notes.map((n) => (n.id === ev.note_id ? withPitch(n, midi, key) : n)),
    locked: { ...st.locked, [ev.note_id]: { string: ev.string, fret } },
  }
}

/** Alt+↑/↓: เปลี่ยน pitch ทีละครึ่งเสียงบนสายเดิม (= ช่อง ±1) */
export function shiftFret(st: State, ev: TabEvent, delta: number, s: TabSettings, key: Parameters<typeof noteName>[1]): State | null {
  return ev.fret === null ? null : setFret(st, ev, ev.fret + delta, s, key)
}

export function toggleLock(st: State, ev: TabEvent): State {
  if (ev.string === null || ev.fret === null) return st
  const locked = { ...st.locked }
  if (locked[ev.note_id]) delete locked[ev.note_id]
  else locked[ev.note_id] = { string: ev.string, fret: ev.fret }
  return { ...st, locked }
}

/** ล็อกตำแหน่งที่ผู้ใช้เลือกเอง (เช่นจากปุ่มทางเลือก) */
export const lockAt = (st: State, noteId: string, pos: FretPos): State => ({ ...st, locked: { ...st.locked, [noteId]: pos } })

export const removeNote = (st: State, noteId: string): State => {
  const locked = { ...st.locked }
  const techniques = { ...st.techniques }
  delete locked[noteId]
  delete techniques[noteId]
  return { notes: st.notes.filter((n) => n.id !== noteId), locked, techniques }
}

export type TechKey = 'hammer' | 'pull' | 'slide' | 'bend' | 'release' | 'vibrato' | 'grace'
/** สลับเทคนิค (กดซ้ำ = ถอด) ตามปุ่มลัดใน plan หัวข้อ 14: H P S B R V G
 *  hammer/pull/slide = เทคนิคไปตัวถัดไป (to_next), bend/vibrato/release = บนโน้ตนี้ (on), grace = นำเข้า (in) */
export function toggleTechnique(st: State, noteId: string, k: TechKey): State {
  const cur: Techniques = { ...(st.techniques[noteId] ?? {}) }
  if (k === 'hammer' || k === 'pull' || k === 'slide') {
    if (cur.to_next === k) delete cur.to_next
    else cur.to_next = k
  } else if (k === 'grace') {
    if (cur.in === 'grace') delete cur.in
    else cur.in = 'grace'
  } else {
    const on = new Set(cur.on ?? [])
    if (on.has(k)) on.delete(k)
    else on.add(k)
    if (on.size) cur.on = [...on]
    else delete cur.on
  }
  const techniques = { ...st.techniques }
  if (Object.keys(cur).length) techniques[noteId] = cur
  else delete techniques[noteId]
  return { ...st, techniques }
}

/** แปลงเทคนิคเป็นสัญลักษณ์ต่อท้ายเลขช่องตามภาคผนวก A (ข้อความสั้น ๆ ที่แสดงข้างเลข) */
export function techniqueMark(t: Techniques | undefined): string {
  if (!t) return ''
  let m = ''
  if (t.in === 'slide_in') m += '/'
  if (t.on?.includes('bend')) m += 'b'
  if (t.on?.includes('release')) m += 'r'
  if (t.on?.includes('vibrato')) m += '~'
  if (t.to_next === 'hammer') m += 'h'
  if (t.to_next === 'pull') m += 'p'
  if (t.to_next === 'slide') m += '/'
  return m
}

/** อัปเดตแทปทันทีแบบ optimistic ระหว่างรอ engine สร้างใหม่: ใช้ตำแหน่งที่ล็อก ทิ้ง event ของโน้ตที่ถูกลบ
 *  (engine จะคำนวณทับทั้งหมดอีกครั้ง ผลนี้เป็นแค่ให้ผู้ใช้เห็นการแก้ไขทันที) */
export function patchEventsOptimistic(events: TabEvent[], notes: Note[], locked: Record<string, FretPos>, s: TabSettings): TabEvent[] {
  const ids = new Set(notes.map((n) => n.id))
  return events
    .filter((e) => ids.has(e.note_id))
    .map((e) => {
      const lk = locked[e.note_id]
      if (!lk) return e.locked ? { ...e, locked: false } : e
      const pitch = pitchAt(s, lk.string, lk.fret)
      return { ...e, string: lk.string, fret: lk.fret, pitch, locked: true, warnings: e.warnings.filter((w) => w === 'out_of_block' || w === 'octave_shifted') }
    })
}

export interface TechSuggestion { techniques: Record<string, Techniques>; bends: Record<string, number>; rejected: { note_id: string; technique: string; reason: string }[]; ornaments: number }

/** รวมเทคนิคที่ระบบเสนอ: ไม่ทับโน้ตที่ผู้ใช้ใส่เทคนิคไว้เอง (คืน State เดิมถ้าไม่มีอะไรเปลี่ยน) */
export function mergeAutoTechniques(st: State, sug: TechSuggestion): { state: State; added: number; skipped: number } {
  const techniques = { ...st.techniques }
  const ids = new Set(st.notes.map((n) => n.id))
  let added = 0
  let skipped = 0
  for (const [id, t] of Object.entries(sug.techniques)) {
    if (!ids.has(id)) continue
    if (techniques[id]) { skipped++; continue }
    techniques[id] = { ...t, ...(sug.bends[id] ? { bend_semitones: sug.bends[id] } : {}) }
    added++
  }
  return { state: added ? { ...st, techniques } : st, added, skipped }
}
