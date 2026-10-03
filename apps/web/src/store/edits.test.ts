import { describe, expect, it } from 'vitest'
import type { Note } from '../types'
import { addNote, mergeNext, movePitch, needsReview, nextReview, remove, setTimes, splitAt } from './edits'

const n = (id: string, midi: number, start: number, end: number, extra: Partial<Note> = {}): Note =>
  ({ id, midi, name: 'x', freq: 0, start, end, cents_offset: 5, confidence: 0.4, octave_suspect: true, edited: false, ...extra })

const base = [n('a', 60, 0, 1), n('b', 62, 1, 2, { confidence: 0.9, octave_suspect: false })]

describe('edits', () => {
  it('movePitch เปลี่ยนชื่อ/ความถี่ และถือว่าคนยืนยันแล้ว', () => {
    const out = movePitch(base, 'a', 12, null)
    expect(out[0]).toMatchObject({ midi: 72, name: 'C5', confidence: 1, octave_suspect: false, edited: true, cents_offset: null })
    expect(out[1]).toBe(base[1])                                   // ตัวอื่นไม่ถูกแตะ
    expect(base[0].midi).toBe(60)                                  // ไม่แก้ array เดิม
  })
  it('movePitch ไม่เกินช่วงเปียโน', () => expect(movePitch(base, 'a', 999, null)[0].midi).toBe(108))
  it('setTimes ขั้นต่ำ 40 ms และไม่ติดลบ', () => {
    const o = setTimes(base, 'a', -1, -0.5, null)[0]
    expect(o.start).toBe(0)
    expect(o.end).toBeCloseTo(0.04)
  })
  it('splitAt แบ่งสองตัวเรียงตามเวลา และปฏิเสธจุดที่ชิดขอบ', () => {
    const out = splitAt(base, 'a', 0.4, null)
    expect(out.map((x) => [x.start, x.end])).toEqual([[0, 0.4], [0.4, 1], [1, 2]])
    expect(new Set(out.map((x) => x.id)).size).toBe(3)
    expect(splitAt(base, 'a', 0.01, null)).toBe(base)
  })
  it('mergeNext รวมกับตัวถัดไป ใช้ pitch ตัวแรก', () => {
    const out = mergeNext(base, 'a', null)
    expect(out).toHaveLength(1)
    expect(out[0]).toMatchObject({ id: 'a', midi: 60, start: 0, end: 2 })
    expect(mergeNext(base, 'b', null)).toBe(base)                  // ตัวสุดท้าย ไม่มีตัวถัดไป
  })
  it('remove / addNote', () => {
    expect(remove(base, 'a').map((x) => x.id)).toEqual(['b'])
    const { notes, id } = addNote(base, 0.5, 66, 0.3, { tonic: 'D', mode: 'major', score: 1, alternatives: [] })
    const added = notes.find((x) => x.id === id)!
    expect(added).toMatchObject({ midi: 66, name: 'F#4', confidence: 1, edited: true })
    expect(notes.map((x) => x.start)).toEqual([0, 0.5, 1])         // เรียงตามเวลา
  })
  it('needsReview / nextReview', () => {
    const list = [n('a', 60, 0, 1), n('b', 62, 1, 2, { confidence: 0.9, octave_suspect: false }), n('c', 64, 2, 3)]
    expect(needsReview(list).map((x) => x.id)).toEqual(['a', 'c'])
    expect(nextReview(list, 0.5, null)?.id).toBe('c')              // ตัวถัดไปหลังเวลา 0.5
    expect(nextReview(list, 0, 'c')?.id).toBe('a')                 // วนกลับต้นเพลง
    expect(nextReview([base[1]], 0, null)).toBeNull()
  })
})
