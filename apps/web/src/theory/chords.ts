import { pcOf } from './notes'

const SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
const FLAT_KEYS_MAJOR = new Set(['F', 'Bb', 'Eb', 'Ab', 'Db', 'Gb', 'A#', 'D#', 'G#'])
const FLAT_KEYS_MINOR = new Set(['D', 'G', 'C', 'F', 'Bb', 'Eb', 'A#', 'D#'])

/** ควรเขียนด้วย ♭ ไหมสำหรับคีย์นี้ (หลัง transpose) */
export function preferFlats(key: { tonic: string; mode: string } | null | undefined, transpose = 0): boolean {
  if (!key) return false
  const t = SHARP[(pcOf(key.tonic) + transpose + 120) % 12]
  return (key.mode === 'minor' ? FLAT_KEYS_MINOR : FLAT_KEYS_MAJOR).has(t)
}

interface Parsed { root: number; suffix: string; bass: number | null }

/** "C#m7/G#" → {root:1, suffix:"m7", bass:8}; "N" หรือข้อความที่ไม่ใช่คอร์ด → null */
export function parseChord(sym: string): Parsed | null {
  const m = /^([A-G][#b]?)([^/]*)(?:\/([A-G][#b]?))?$/.exec(sym.trim())
  if (!m) return null
  const root = pcOf(m[1])
  if (root < 0) return null
  const bass = m[3] ? pcOf(m[3]) : null
  return { root, suffix: m[2], bass: bass !== null && bass >= 0 ? bass : null }
}

/** ยกคอร์ดขึ้น/ลง semitone (ใช้ทั้ง transpose และแสดงรูปมือหลัง capo = transpose ลบ capo) */
export function transposeChord(sym: string, semis: number, flats = false): string {
  const p = parseChord(sym)
  if (!p) return sym
  const names = flats ? FLAT : SHARP
  const n = (x: number) => names[(((x + semis) % 12) + 12) % 12]
  return n(p.root) + p.suffix + (p.bass !== null ? '/' + n(p.bass) : '')
}

/** ชื่อคอร์ดที่เขียนด้วย ♯ ภายใน → ตามความชอบ ♯/♭ (ไม่ยก) */
export const spellChord = (sym: string, flats: boolean) => transposeChord(sym, 0, flats)

/** โน้ตในคอร์ด (pitch class) จาก suffix ที่รู้จัก — ใช้ตรวจความถูกต้องของไดอะแกรม */
export function chordTones(sym: string): Set<number> | null {
  const p = parseChord(sym)
  if (!p) return null
  const table: Record<string, number[]> = {
    '': [0, 4, 7], m: [0, 3, 7], '7': [0, 4, 7, 10], maj7: [0, 4, 7, 11], m7: [0, 3, 7, 10], dim: [0, 3, 6], aug: [0, 4, 8],
    sus4: [0, 5, 7], sus2: [0, 2, 7], '6': [0, 4, 7, 9], m6: [0, 3, 7, 9], dim7: [0, 3, 6, 9], m7b5: [0, 3, 6, 10], 'm(maj7)': [0, 3, 7, 11],
  }
  const t = table[p.suffix]
  if (!t) return null
  const s = new Set(t.map((x) => (p.root + x) % 12))
  if (p.bass !== null) s.add(p.bass)
  return s
}
