import { describe, expect, it } from 'vitest'
import { chordTones, parseChord, preferFlats, spellChord, transposeChord } from './chords'
import { shapeFor, shapeIsValid } from './chordShapes'

describe('chord names', () => {
  it('parseChord', () => {
    expect(parseChord('C#m7/G#')).toEqual({ root: 1, suffix: 'm7', bass: 8 })
    expect(parseChord('Bb')).toEqual({ root: 10, suffix: '', bass: null })
    expect(parseChord('N')).toBeNull()
    expect(parseChord('hello')).toBeNull()
  })
  it('transposeChord ยก/ลง และรักษา slash + quality', () => {
    expect(transposeChord('D', 2)).toBe('E')
    expect(transposeChord('Bm7', 3)).toBe('Dm7')
    expect(transposeChord('C/E', 2)).toBe('D/F#')
    expect(transposeChord('A', -2)).toBe('G')
    expect(transposeChord('C', 1, true)).toBe('Db')
    expect(transposeChord('N', 5)).toBe('N')
    expect(spellChord('A#', true)).toBe('Bb')
  })
  it('capo: รูปมือ = transpose ลบ capo', () => {
    // เสียงจริง D, G, A เมื่อติด capo 2 เล่นรูป C, F, G
    expect(['D', 'G', 'A'].map((c) => transposeChord(c, -2))).toEqual(['C', 'F', 'G'])
  })
  it('preferFlats ตามคีย์หลัง transpose', () => {
    expect(preferFlats({ tonic: 'F', mode: 'major' })).toBe(true)
    expect(preferFlats({ tonic: 'D', mode: 'major' })).toBe(false)
    expect(preferFlats({ tonic: 'D', mode: 'major' }, 3)).toBe(true) // D + 3 = F
    expect(preferFlats(null)).toBe(false)
  })
  it('chordTones', () => {
    expect([...chordTones('Am7')!].sort((a, b) => a - b)).toEqual([0, 4, 7, 9])
    expect(chordTones('Zzz')).toBeNull()
  })
})

describe('chord shapes — ตรวจโน้ตที่ดีดจริงทุกทรง', () => {
  const roots = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
  const suffixes = ['', 'm', '7', 'maj7', 'm7', 'sus4']
  it('ทุก root × quality ที่มีทรง ต้องดีดแต่โน้ตในคอร์ด และโน้ตต่ำสุดเป็น root', () => {
    let have = 0
    for (const r of roots) {
      for (const q of suffixes) {
        const sym = r + q
        const s = shapeFor(sym)
        if (!s) continue
        have++
        expect(shapeIsValid(sym, s), `${sym} frets=${s.frets}`).toBe(true)
      }
    }
    expect(have).toBeGreaterThanOrEqual(roots.length * suffixes.length * 0.9) // ครอบคลุมเกือบทุกคอร์ดพื้นฐาน
  })
  it('คอร์ดเปิดยอดนิยมใช้ทรงเปิด และคอร์ดอื่นใช้ barre', () => {
    expect(shapeFor('G')?.open).toBe(true)
    expect(shapeFor('F#m')?.open).toBe(false)
    expect(shapeFor('F#m')?.barre).toBeDefined()
    expect(shapeFor('C#7')).not.toBeNull()
  })
  it('คอร์ดที่ไม่รู้จักคืน null ไม่ล้ม', () => {
    expect(shapeFor('N')).toBeNull()
    expect(shapeFor('Cm(maj7)')).toBeNull()
  })
  it('slash chord ใช้ทรงของคอร์ดหลัก', () => {
    expect(shapeFor('D/F#')?.frets).toEqual(shapeFor('D')?.frets)
  })
})
