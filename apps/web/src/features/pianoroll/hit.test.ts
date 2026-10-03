import { describe, expect, it } from 'vitest'
import type { Note } from '../../types'
import { hitNote } from './PianoRoll'

const n = (id: string, midi: number, start: number, end: number): Note =>
  ({ id, midi, name: '', freq: 0, start, end, cents_offset: null, confidence: 1, octave_suspect: false, edited: false })

describe('hitNote', () => {
  const notes = [n('a', 60, 0, 1), n('b', 62, 1, 2)]
  it('เจอโน้ตที่ตรงทั้งเวลาและ pitch', () => expect(hitNote(notes, 0.5, 60)?.id).toBe('a'))
  it('pitch ไม่ตรง = ไม่เจอ', () => expect(hitNote(notes, 0.5, 61)).toBeNull())
  it('นอกช่วงเวลา = ไม่เจอ', () => expect(hitNote(notes, 3, 62)).toBeNull())
})
