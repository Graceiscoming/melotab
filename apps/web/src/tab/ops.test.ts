import { describe, expect, it } from 'vitest'
import type { Note, TabEvent, TabSettings } from '../types'
import { mergeAutoTechniques, fretFor, lockAt, moveString, patchEventsOptimistic, pitchAt, removeNote, setFret, shiftFret, techniqueMark, toggleLock, toggleTechnique, type State } from './ops'

const S: TabSettings = { transpose: 0, capo: 0, tuning: 'standard', max_fret: 22, blocks: [], block_mode: 'multi', out_of_block: 'octave_shift', preset: 'balanced' }
const note = (id: string, midi: number): Note => ({ id, midi, name: '', freq: 0, start: 0, end: 1, cents_offset: null, confidence: 0.3, octave_suspect: true, edited: false })
const ev = (noteId: string, string: number, fret: number, pitch: number): TabEvent => ({
  id: 't_' + noteId, note_id: noteId, pitch, string, fret, start: 0, end: 1, start_beat: 0, dur_beats: 1, techniques: {}, bend: null, finger: null,
  locked: false, difficulty: 0, warnings: [],
})
const st = (): State => ({ notes: [note('a', 64)], locked: {}, techniques: {} })

describe('tab ops', () => {
  it('pitchAt / fretFor ตามจูนนิ่งและ capo', () => {
    expect(pitchAt(S, 1, 0)).toBe(64)
    expect(pitchAt(S, 6, 3)).toBe(43)
    expect(pitchAt({ ...S, capo: 2 }, 1, 0)).toBe(66)
    expect(pitchAt({ ...S, tuning: 'drop_d' }, 6, 0)).toBe(38)
    expect(fretFor(S, 2, 64)).toBe(5)
    expect(fretFor(S, 1, 60)).toBeNull()                    // ต่ำกว่าสายเปล่า
    expect(fretFor({ ...S, max_fret: 12 }, 1, 80)).toBeNull()
  })
  it('moveString รักษา pitch เดิม และล็อกตำแหน่งใหม่', () => {
    const e = ev('a', 1, 0, 64)
    const down = moveString(st(), e, 1, S)!               // สาย 1 → สาย 2: ช่อง 5
    expect(down.locked.a).toEqual({ string: 2, fret: 5 })
    expect(pitchAt(S, 2, 5)).toBe(64)
    expect(moveString(st(), e, -1, S)).toBeNull()           // ไม่มีสายเหนือสาย 1
    expect(moveString(st(), ev('a', 6, 24, 64), 1, S)).toBeNull()
  })
  it('setFret เปลี่ยน pitch ของโน้ตและล้างสถานะ "สงสัย" (คนยืนยันแล้ว)', () => {
    const r = setFret(st(), ev('a', 2, 5, 64), 7, S, null)!
    expect(r.notes[0]).toMatchObject({ midi: 66, name: 'F#4', edited: true, confidence: 1, octave_suspect: false })
    expect(r.locked.a).toEqual({ string: 2, fret: 7 })
    expect(setFret(st(), ev('a', 2, 5, 64), 99, S, null)).toBeNull()
  })
  it('setFret พิจารณา transpose: โน้ตเดิม = pitch − transpose', () => {
    const r = setFret(st(), ev('a', 2, 7, 66), 9, { ...S, transpose: 2 }, null)!   // สาย 2 ช่อง 9 = pitch 68 (เสียงหลัง transpose)
    expect(r.notes[0].midi).toBe(66)                        // โน้ตเดิม = 68 − 2
  })
  it('shiftFret = ช่อง ±1 บนสายเดิม', () => {
    expect(shiftFret(st(), ev('a', 2, 5, 64), 1, S, null)!.notes[0].midi).toBe(65)
    expect(shiftFret(st(), ev('a', 2, 0, 59), -1, S, null)).toBeNull()
  })
  it('toggleLock / lockAt / removeNote', () => {
    const e = ev('a', 2, 5, 64)
    const locked = toggleLock(st(), e)
    expect(locked.locked.a).toEqual({ string: 2, fret: 5 })
    expect(toggleLock(locked, e).locked.a).toBeUndefined()
    expect(lockAt(st(), 'a', { string: 3, fret: 9 }).locked.a.fret).toBe(9)
    const removed = removeNote({ ...locked, techniques: { a: { to_next: 'hammer' } } }, 'a')
    expect(removed.notes).toHaveLength(0)
    expect(removed.locked.a).toBeUndefined()
    expect(removed.techniques.a).toBeUndefined()
  })
  it('toggleTechnique: กดซ้ำ = ถอด, สัญลักษณ์ตามภาคผนวก A', () => {
    let s = toggleTechnique(st(), 'a', 'hammer')
    expect(techniqueMark(s.techniques.a)).toBe('h')
    s = toggleTechnique(s, 'a', 'pull')                     // สลับเป็น pull (to_next เดียว)
    expect(techniqueMark(s.techniques.a)).toBe('p')
    s = toggleTechnique(s, 'a', 'vibrato')
    expect(techniqueMark(s.techniques.a)).toBe('~p')
    s = toggleTechnique(toggleTechnique(s, 'a', 'pull'), 'a', 'vibrato')
    expect(s.techniques.a).toBeUndefined()                  // ถอดหมด = ไม่เก็บ object ว่าง
    expect(techniqueMark(toggleTechnique(st(), 'a', 'bend').techniques.a)).toBe('b')
  })
})

describe('patchEventsOptimistic', () => {
  it('ใช้ตำแหน่งที่ล็อกทันที ทิ้ง event ของโน้ตที่ถูกลบ และปลดธง locked ที่ไม่มีล็อกแล้ว', () => {
    const events = [ev('a', 1, 0, 64), { ...ev('b', 2, 5, 64), locked: true }, ev('c', 3, 9, 64)]
    const notes = [note('a', 64), note('b', 64)]                         // c ถูกลบแล้ว
    const out = patchEventsOptimistic(events, notes, { a: { string: 2, fret: 5 } }, S)
    expect(out.map((e) => e.note_id)).toEqual(['a', 'b'])
    expect(out[0]).toMatchObject({ string: 2, fret: 5, pitch: 64, locked: true })
    expect(out[1].locked).toBe(false)                                    // b เคยล็อกแต่ตอนนี้ไม่มีใน locked แล้ว
  })
})

describe('mergeAutoTechniques', () => {
  it('ไม่ทับเทคนิคที่ผู้ใช้ใส่เอง และเก็บปริมาณ bend', () => {
    const base: State = { notes: [note('a', 64), note('b', 66), note('z', 60)], locked: {}, techniques: { a: { on: ['vibrato'] } } }
    const sug = { techniques: { a: { to_next: 'hammer' }, b: { on: ['bend'] }, gone: { on: ['vibrato'] } }, bends: { b: 2 }, rejected: [], ornaments: 3 }
    const r = mergeAutoTechniques(base, sug)
    expect(r.added).toBe(1)
    expect(r.skipped).toBe(1)
    expect(r.state.techniques.a).toEqual({ on: ['vibrato'] })
    expect(r.state.techniques.b).toEqual({ on: ['bend'], bend_semitones: 2 })
    expect(r.state.techniques.gone).toBeUndefined()
    expect(mergeAutoTechniques(r.state, sug).state).toBe(r.state)
  })
  it('slide_in แสดง / นำหน้า', () => { expect(techniqueMark({ in: 'slide_in', on: ['vibrato'] })).toBe('/~') })
})
