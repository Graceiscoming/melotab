import { shapeFor } from '../../theory/chordShapes'

const STR_X = (i: number) => 14 + i * 14 // สาย 6 → 1 ซ้าย → ขวา
const FRET_Y = (f: number) => 26 + f * 16
const NAMES_OPEN = ['E', 'A', 'D', 'G', 'B', 'E']

/** ไดอะแกรมทรงคอร์ด (Standard tuning) — ไม่มีทรงที่รู้จักจะบอกตรง ๆ */
export function ChordDiagram({ symbol, title }: { symbol: string; title?: string }) {
  const shape = shapeFor(symbol)
  if (!shape) return <div className="diagram none">ไม่มีทรงสำหรับ {symbol}</div>
  const base = shape.open ? 1 : shape.baseFret
  const rows = 5
  return (
    <svg width={100} height={112} className="diagram" data-testid="chord-diagram" data-symbol={symbol}>
      <text x={50} y={12} textAnchor="middle" fontSize={13} fontWeight={700} fill="#e6e9f0">{title ?? symbol}</text>
      {shape.open ? <rect x={14} y={FRET_Y(0) - 2} width={70} height={3} fill="#c9cfdd" /> : <text x={2} y={FRET_Y(0) + 12} fontSize={10} fill="#8b93a7">{base}</text>}
      {Array.from({ length: rows + 1 }, (_, f) => <line key={f} x1={14} x2={84} y1={FRET_Y(f)} y2={FRET_Y(f)} stroke="#4a5266" strokeWidth={1} />)}
      {[0, 1, 2, 3, 4, 5].map((i) => <line key={i} x1={STR_X(i)} x2={STR_X(i)} y1={FRET_Y(0)} y2={FRET_Y(rows)} stroke="#6f7a92" strokeWidth={1} />)}
      {shape.barre && !shape.open && (
        <rect x={STR_X(6 - shape.barre.from) - 5} y={FRET_Y(shape.barre.fret - base) + 3} width={STR_X(5) - STR_X(6 - shape.barre.from) + 10} height={10} rx={5} fill="#5aa9ff" opacity={0.9} />
      )}
      {shape.frets.map((f, i) => {
        if (f < 0) return <text key={i} x={STR_X(i)} y={FRET_Y(0) - 6} textAnchor="middle" fontSize={11} fill="#ff6b81">×</text>
        if (f === 0) return <circle key={i} cx={STR_X(i)} cy={FRET_Y(0) - 8} r={3.5} fill="none" stroke="#8b93a7" />
        const row = f - base
        if (row < 0 || row >= rows) return null
        return <circle key={i} cx={STR_X(i)} cy={FRET_Y(row) + 8} r={5} fill="#5aa9ff"><title>สาย {NAMES_OPEN[i]} ช่อง {f}</title></circle>
      })}
    </svg>
  )
}
