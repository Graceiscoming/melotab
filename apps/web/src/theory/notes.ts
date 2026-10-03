const SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
// คีย์ที่นิยมเขียนด้วย ♭ (เมเจอร์: F Bb Eb Ab Db Gb / ไมเนอร์: D G C F Bb Eb)
const FLAT_MAJOR = new Set(['F', 'Bb', 'Eb', 'Ab', 'Db', 'Gb', 'A#', 'D#', 'G#'])
const FLAT_MINOR = new Set(['D', 'G', 'C', 'F', 'Bb', 'Eb', 'A#', 'D#'])
const MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
const MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]

export const BLACK = new Set([1, 3, 6, 8, 10])
export const pcOf = (name: string): number => {
  const i = SHARP.indexOf(name)
  return i >= 0 ? i : FLAT.indexOf(name)
}

/** ชื่อโน้ตแบบ Scientific Pitch (C4 = 60) เลือก ♯/♭ ตามคีย์ */
export function noteName(midi: number, key?: { tonic: string; mode: string } | null): string {
  const useFlat = key ? (key.mode === 'major' ? FLAT_MAJOR : FLAT_MINOR).has(key.tonic) : false
  const pc = ((midi % 12) + 12) % 12
  return (useFlat ? FLAT : SHARP)[pc] + (Math.floor(midi / 12) - 1)
}

export function scalePcs(key: { tonic: string; mode: string } | null): Set<number> {
  if (!key) return new Set()
  const t = pcOf(key.tonic)
  return new Set((key.mode === 'minor' ? MINOR_SCALE : MAJOR_SCALE).map((d) => (t + d) % 12))
}

export const midiToHz = (m: number) => 440 * 2 ** ((m - 69) / 12)
