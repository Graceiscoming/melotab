import { describe, expect, it } from 'vitest'
import { noteName, pcOf, scalePcs } from './notes'

describe('noteName', () => {
  it('ใช้ Scientific Pitch (C4 = 60, A4 = 69)', () => {
    expect(noteName(60)).toBe('C4')
    expect(noteName(69)).toBe('A4')
    expect(noteName(66)).toBe('F#4')
  })
  it('เลือก ♯/♭ ตามคีย์', () => {
    expect(noteName(70, { tonic: 'F', mode: 'major' })).toBe('Bb4')
    expect(noteName(70, { tonic: 'D', mode: 'major' })).toBe('A#4')
    expect(noteName(63, { tonic: 'C', mode: 'minor' })).toBe('Eb4')
  })
})

describe('scalePcs', () => {
  it('D major = D E F# G A B C#', () => {
    const s = scalePcs({ tonic: 'D', mode: 'major' })
    expect([...s].sort((a, b) => a - b)).toEqual([1, 2, 4, 6, 7, 9, 11])
    expect(pcOf('Bb')).toBe(10)
  })
  it('ไม่มีคีย์ = เซตว่าง', () => expect(scalePcs(null).size).toBe(0))
})
