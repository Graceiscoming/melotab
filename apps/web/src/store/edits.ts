import { midiToHz, noteName } from '../theory/notes'
import type { KeyInfo, Note } from '../types'

/** ตัวช่วยแก้โน้ตแบบ pure function (ไม่แตะ array เดิม) — ใช้กับ undo/redo ผ่าน snapshot ของ array ทั้งชุด */

const MIN_DUR = 0.04
const MIDI_MIN = 21
const MIDI_MAX = 108

let uid = 0
export const newId = () => `u${Date.now().toString(36)}${(uid++).toString(36)}`

const clampMidi = (m: number) => Math.max(MIDI_MIN, Math.min(MIDI_MAX, Math.round(m)))

/** โน้ตที่ผู้ใช้แก้ถือว่ามั่นใจ 100% และไม่สงสัย octave อีก (คนยืนยันแล้ว) */
function touched(n: Note, key: KeyInfo | null, patch: Partial<Note>): Note {
  const merged = { ...n, ...patch }
  return {
    ...merged,
    name: noteName(merged.midi, key),
    freq: Math.round(midiToHz(merged.midi) * 100) / 100,
    confidence: 1,
    octave_suspect: false,
    octave_fixed: false,
    edited: true,
    cents_offset: patch.midi !== undefined ? null : n.cents_offset,
  } as Note
}

const sorted = (notes: Note[]) => [...notes].sort((a, b) => a.start - b.start || a.midi - b.midi)

export function movePitch(notes: Note[], id: string, delta: number, key: KeyInfo | null): Note[] {
  return notes.map((n) => (n.id === id ? touched(n, key, { midi: clampMidi(n.midi + delta) }) : n))
}

export function setPitch(notes: Note[], id: string, midi: number, key: KeyInfo | null): Note[] {
  return notes.map((n) => (n.id === id ? touched(n, key, { midi: clampMidi(midi) }) : n))
}

/** ตั้งเวลาเริ่ม/จบ (ความยาวต่ำสุด 40 ms) */
export function setTimes(notes: Note[], id: string, start: number, end: number, key: KeyInfo | null): Note[] {
  const s = Math.max(0, start)
  const e = Math.max(s + MIN_DUR, end)
  return sorted(notes.map((n) => (n.id === id ? touched(n, key, { start: s, end: e }) : n)))
}

/** แบ่งโน้ตที่เวลา t เป็นสองตัว (ต้องอยู่ภายในโน้ต เหลือความยาวอย่างน้อยฝั่งละ 40 ms) */
export function splitAt(notes: Note[], id: string, t: number, key: KeyInfo | null): Note[] {
  const n = notes.find((x) => x.id === id)
  if (!n || t - n.start < MIN_DUR || n.end - t < MIN_DUR) return notes
  const a = touched(n, key, { end: t })
  const b = { ...touched(n, key, { start: t }), id: newId() }
  return sorted([...notes.filter((x) => x.id !== id), a, b])
}

/** รวมโน้ตกับตัวถัดไปในเวลา (ใช้ pitch ของตัวแรก) */
export function mergeNext(notes: Note[], id: string, key: KeyInfo | null): Note[] {
  const s = sorted(notes)
  const i = s.findIndex((x) => x.id === id)
  if (i < 0 || i >= s.length - 1) return notes
  const merged = touched(s[i], key, { end: Math.max(s[i].end, s[i + 1].end) })
  return s.flatMap((x, j) => (j === i ? [merged] : j === i + 1 ? [] : [x]))
}

export function remove(notes: Note[], id: string): Note[] {
  return notes.filter((n) => n.id !== id)
}

export function addNote(notes: Note[], start: number, midi: number, dur: number, key: KeyInfo | null): { notes: Note[]; id: string } {
  const id = newId()
  const n = touched({ id, midi: clampMidi(midi), name: '', freq: 0, start, end: start + Math.max(MIN_DUR, dur),
    cents_offset: null, confidence: 1, octave_suspect: false, edited: true } as Note, key, {})
  return { notes: sorted([...notes, n]), id }
}

/** โน้ตที่ควรตรวจ (confidence ต่ำ หรือสงสัย octave) เรียงตามเวลา */
export function needsReview(notes: Note[]): Note[] {
  return sorted(notes).filter((n) => n.confidence < 0.5 || n.octave_suspect)
}

/** หาโน้ตที่ควรตรวจ "ถัดไป" หลังเวลา t (วนกลับต้นเพลงเมื่อหมด); คืน null ถ้าไม่มีเลย */
export function nextReview(notes: Note[], t: number, selectedId: string | null): Note | null {
  const list = needsReview(notes)
  if (list.length === 0) return null
  const cur = list.findIndex((n) => n.id === selectedId)
  if (cur >= 0) return list[(cur + 1) % list.length]
  return list.find((n) => n.start > t) ?? list[0]
}
