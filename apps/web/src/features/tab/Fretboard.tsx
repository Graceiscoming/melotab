import type { Block, TabEvent } from '../../types'

const FRETS = 22
const W = 336
const LEFT = 18
const FW = (W - LEFT - 6) / FRETS
const SG = 14 // ระยะห่างสาย
const H = 6 * SG + 22
const MARKS = [3, 5, 7, 9, 12, 15, 17, 19, 21]
const NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

interface Props {
  blocks: Block[] // block ที่เลือก (ไฮไลต์ช่วงช่อง)
  tuning: number[] // MIDI สาย 6 → 1
  capo: number
  pcs: Set<number> // โน้ตของสเกลที่แสดงเป็นจุด
  tonicPc: number | null
  selected?: TabEvent | null
}

/** Fretboard ย่อ: แสดงช่วง block ที่เลือก จุดสเกล และตำแหน่งของโน้ตที่เลือกในแทป (ช่องนับจาก capo) */
export function Fretboard({ blocks, tuning, capo, pcs, tonicPc, selected }: Props) {
  const x = (fret: number) => LEFT + (fret === 0 ? -FW / 2 + 4 : (fret - 0.5) * FW)
  const y = (string: number) => 12 + (string - 1) * SG
  return (
    <svg width={W} height={H} className="fretboard" data-testid="fretboard">
      {blocks.map((b) => (
        <rect key={b.id} x={LEFT + (b.fret_min - 1) * FW + (b.fret_min === 0 ? FW * 0 : 0)} y={6} width={(b.fret_max - Math.max(b.fret_min, 1) + 1) * FW + (b.fret_min === 0 ? FW : 0)}
          height={6 * SG} rx={4} fill="#5aa9ff" opacity={0.16} stroke="#5aa9ff" strokeOpacity={0.6} />
      ))}
      {Array.from({ length: FRETS + 1 }, (_, f) => (
        <line key={f} x1={LEFT + f * FW} x2={LEFT + f * FW} y1={12} y2={12 + 5 * SG} stroke={f === 0 ? '#c9cfdd' : '#3b4252'} strokeWidth={f === 0 ? 3 : 1} />
      ))}
      {[1, 2, 3, 4, 5, 6].map((s) => <line key={s} x1={LEFT} x2={LEFT + FRETS * FW} y1={y(s)} y2={y(s)} stroke="#6f7a92" strokeWidth={1 + (s - 1) * 0.25} />)}
      {MARKS.map((f) => <text key={f} x={LEFT + (f - 0.5) * FW} y={H - 3} fontSize={9} fill="#6f7a92" textAnchor="middle">{f}</text>)}
      {[1, 2, 3, 4, 5, 6].flatMap((s) =>
        Array.from({ length: FRETS + 1 }, (_, f) => {
          const pc = (tuning[6 - s] + capo + f) % 12
          if (!pcs.has(pc)) return null
          const root = tonicPc === pc
          return <circle key={`${s}-${f}`} cx={x(f)} cy={y(s)} r={root ? 4.2 : 3} fill={root ? '#ffd666' : '#8b93a7'} opacity={root ? 1 : 0.7}><title>{NAMES[pc]}</title></circle>
        }))}
      {selected && selected.string !== null && selected.fret !== null && (
        <circle cx={x(selected.fret)} cy={y(selected.string)} r={6} fill="none" stroke="#ff5c7a" strokeWidth={2.5} data-testid="fretboard-selected" />
      )}
    </svg>
  )
}
