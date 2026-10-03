import { chordTones, parseChord } from './chords'

/** ทรงคอร์ดกีตาร์ (Standard tuning): frets เรียงสาย 6→1, -1 = ไม่ดีด, 0 = สายเปล่า; baseFret = ช่องแรกของไดอะแกรม (1 = ติดนัท) */
export interface Shape { frets: number[]; baseFret: number; barre?: { fret: number; from: number; to: number }; open: boolean }

const OPEN: Record<string, number[]> = {
  C: [-1, 3, 2, 0, 1, 0], D: [-1, -1, 0, 2, 3, 2], E: [0, 2, 2, 1, 0, 0], G: [3, 2, 0, 0, 0, 3], A: [-1, 0, 2, 2, 2, 0],
  Am: [-1, 0, 2, 2, 1, 0], Dm: [-1, -1, 0, 2, 3, 1], Em: [0, 2, 2, 0, 0, 0],
  C7: [-1, 3, 2, 3, 1, 0], D7: [-1, -1, 0, 2, 1, 2], E7: [0, 2, 0, 1, 0, 0], G7: [3, 2, 0, 0, 0, 1], A7: [-1, 0, 2, 0, 2, 0], B7: [-1, 2, 1, 2, 0, 2],
  Cmaj7: [-1, 3, 2, 0, 0, 0], Dmaj7: [-1, -1, 0, 2, 2, 2], Fmaj7: [-1, -1, 3, 2, 1, 0], Gmaj7: [3, 2, 0, 0, 0, 2], Amaj7: [-1, 0, 2, 1, 2, 0], Emaj7: [0, 2, 1, 1, 0, 0],
  Am7: [-1, 0, 2, 0, 1, 0], Dm7: [-1, -1, 0, 2, 1, 1], Em7: [0, 2, 0, 0, 0, 0],
  Asus2: [-1, 0, 2, 2, 0, 0], Asus4: [-1, 0, 2, 2, 3, 0], Dsus2: [-1, -1, 0, 2, 3, 0], Dsus4: [-1, -1, 0, 2, 3, 3], Esus4: [0, 2, 2, 2, 0, 0],
}

// รูปเคลื่อนที่ได้ (สัมพัทธ์กับ "ช่อง root"): E-shape (root สาย 6) และ A-shape (root สาย 5) ค่า = offset จาก root fret, null = ไม่ดีด
const E_SHAPE: Record<string, (number | null)[]> = {
  '': [0, 2, 2, 1, 0, 0], m: [0, 2, 2, 0, 0, 0], '7': [0, 2, 0, 1, 0, 0], maj7: [0, 2, 1, 1, 0, 0], m7: [0, 2, 0, 0, 0, 0],
  sus4: [0, 2, 2, 2, 0, 0], '6': [0, 2, 2, 1, 2, 0], m6: [0, 2, 2, 0, 2, 0],
}
const A_SHAPE: Record<string, (number | null)[]> = {
  '': [null, 0, 2, 2, 2, 0], m: [null, 0, 2, 2, 1, 0], '7': [null, 0, 2, 0, 2, 0], maj7: [null, 0, 2, 1, 2, 0], m7: [null, 0, 2, 0, 1, 0],
  sus4: [null, 0, 2, 2, 3, 0], sus2: [null, 0, 2, 2, 0, 0], '6': [null, 0, 2, 2, 2, 2], m6: [null, 0, 2, 2, 1, 2],
  dim: [null, 0, 1, 2, 1, null], m7b5: [null, 0, 1, 0, 1, null],
}
const OPEN_STRINGS = [4, 9, 2, 7, 11, 4] // pitch class ของสาย 6→1

/** หาทรงคอร์ดที่เล่นได้จริง: ใช้ทรงเปิดถ้ามี ไม่งั้นใช้ barre ของ E-/A-shape ที่ช่องต่ำกว่า; null ถ้าไม่มีทรงที่รู้จัก */
export function shapeFor(symbol: string): Shape | null {
  const p = parseChord(symbol)
  if (!p) return null
  const base = symbol.split('/')[0]
  const open = OPEN[base]
  if (open) return { frets: open, baseFret: 1, open: true }
  const cands: Shape[] = []
  const tryShape = (shape: (number | null)[] | undefined, rootString: 6 | 5) => {
    if (!shape) return
    const rootPc = OPEN_STRINGS[6 - rootString]
    const f = (p.root - rootPc + 12) % 12 || 12 // ช่องของ root (สายเปล่าที่ตรง root ใช้ช่อง 12 เพื่อให้เป็น barre)
    const frets = shape.map((o) => (o === null ? -1 : f + o))
    if (Math.max(...frets) > 15) return
    const fretted = frets.filter((x) => x > 0)
    cands.push({ frets, baseFret: Math.min(...fretted), barre: { fret: f, from: rootString, to: 1 }, open: false })
  }
  const suffix = base.replace(/^[A-G][#b]?/, '')
  tryShape(E_SHAPE[suffix], 6)
  tryShape(A_SHAPE[suffix], 5)
  if (cands.length === 0) return null
  return cands.sort((a, b) => a.baseFret - b.baseFret)[0]
}

/** pitch class ของโน้ตที่ดีดตามทรง (-1 = ไม่ดีด) */
export function shapePitchClasses(s: Shape): number[] {
  return s.frets.map((f, i) => (f < 0 ? -1 : (OPEN_STRINGS[i] + f) % 12))
}

/** ทรงถูกต้องไหม: ทุกโน้ตที่ดีดอยู่ในคอร์ด และโน้ตต่ำสุดที่ดีดเป็น root */
export function shapeIsValid(symbol: string, s: Shape): boolean {
  const tones = chordTones(symbol)
  const p = parseChord(symbol)
  if (!tones || !p) return false
  const pcs = shapePitchClasses(s)
  const played = pcs.filter((x) => x >= 0)
  if (!played.every((x) => tones.has(x))) return false
  const lowest = pcs.find((x) => x >= 0)!
  return lowest === p.root
}
