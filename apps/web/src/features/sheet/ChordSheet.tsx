import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { getTransport } from '../../audio/instance'
import { activeRow, buildSheet, type SheetChord } from '../../sheet/build'
import { useStore } from '../../store/store'
import { parseChord, preferFlats, spellChord, transposeChord } from '../../theory/chords'
import { ChordDiagram } from './ChordDiagram'
import { SongPanels } from './SongPanels'

const NOSPACE = (t: string) => /[฀-๿]/.test(t) // ภาษาไทยไม่เว้นวรรคระหว่างคำ

/** Chord Sheet แบบเว็บแจกคอร์ด: คอร์ดอยู่บน เนื้อร้องอยู่ล่าง จัดตามท่อน; ตามเพลง/ไฮไลต์แถวที่กำลังเล่น; transpose + capo */
export function ChordSheet() {
  const song = useStore((s) => s.song)
  const view = useStore((s) => s.view)
  const patchSong = useStore((s) => s.patchSong)
  const tr = getTransport()
  const [transpose, setTranspose] = useState(0)
  const [capo, setCapo] = useState(0)
  const [shapes, setShapes] = useState(true) // แสดงรูปมือหลังติด capo (ปิด = แสดงเสียงจริง)
  const [dedupe, setDedupe] = useState(false)
  const [size, setSize] = useState(16)
  const [pop, setPop] = useState<{ symbol: string; x: number; y: number } | null>(null)
  const [editing, setEditing] = useState<{ start: number; value: string } | null>(null)
  const [active, setActive] = useState<{ section: number; row: number } | null>(null)
  const wrap = useRef<HTMLDivElement>(null)

  const sheet = useMemo(() => (song ? buildSheet(song, { dedupe }) : []), [song, dedupe])
  const flats = preferFlats(song?.key, transpose - (shapes ? capo : 0))

  // ไฮไลต์แถวที่กำลังเล่น + เลื่อนตาม (poll ที่ 10 Hz พอสำหรับการอ่าน ไม่ต้องทุกเฟรม)
  useEffect(() => {
    const id = setInterval(() => {
      const a = activeRow(sheet, tr.getTime())
      setActive((cur) => (cur && a && cur.section === a.section && cur.row === a.row ? cur : a))
    }, 100)
    return () => clearInterval(id)
  }, [sheet, tr])
  useEffect(() => {
    if (!active || !view.follow || !tr.playing) return
    wrap.current?.querySelector(`[data-row="${active.section}-${active.row}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [active, view.follow, tr])

  if (!song) return null
  const show = (c: SheetChord) => {
    const semis = transpose - (shapes ? capo : 0)
    return transposeChord(c.symbol, semis, flats)
  }
  const hasData = (song.chords?.length ?? 0) > 0

  function commitEdit() {
    if (!editing) return
    const v = editing.value.trim()
    patchSong((s) => ({
      ...s,
      chords: (s.chords ?? []).flatMap((c) => {
        if (Math.abs(c.start - editing.start) > 1e-6) return [c]
        if (v === '') return [] // ลบคอร์ด
        if (!parseChord(v)) return [c] // พิมพ์ผิดรูปแบบ → ไม่แก้
        // ที่แก้คือชื่อที่ "แสดง" (หลัง transpose/capo) → แปลงกลับเป็นคอร์ดต้นฉบับ (เก็บแบบ ♯ ภายใน) ก่อนบันทึก
        const symbol = transposeChord(v, -(transpose - (shapes ? capo : 0)), false)
        const p = parseChord(symbol)!
        return [{ ...c, symbol, root: p.root, bass: p.bass !== null ? transposeChord(symbol.split('/')[1] ?? '', 0) : null, edited: true }]
      }),
    }))
    setEditing(null)
  }

  const chord = (c: SheetChord, key: string) => (
    <span key={key} className="chordtag" data-testid="sheet-chord"
      onClick={(e) => { e.stopPropagation(); const r = (e.target as HTMLElement).getBoundingClientRect(); setPop({ symbol: show(c).split('/')[0], x: r.left, y: r.bottom }) }}
      onDoubleClick={(e) => { e.stopPropagation(); setPop(null); setEditing({ start: c.start, value: show(c) }) }}>
      {editing && Math.abs(editing.start - c.start) < 1e-6 ? (
        <input autoFocus value={editing.value} size={Math.max(3, editing.value.length)} className="chordedit"
          onChange={(e) => setEditing({ ...editing, value: e.target.value })} onBlur={commitEdit}
          onKeyDown={(e) => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditing(null) }} />
      ) : show(c)}
    </span>
  )

  return (
    <div className="sheetwrap" ref={wrap} data-testid="chordsheet" onClick={() => setPop(null)}>
      <div className="sheettools">
        <label>Transpose
          <button onClick={() => setTranspose(transpose - 1)} data-testid="tr-minus">−</button>
          <b data-testid="tr-val" style={{ minWidth: 28, textAlign: 'center' }}>{transpose > 0 ? '+' : ''}{transpose}</b>
          <button onClick={() => setTranspose(transpose + 1)} data-testid="tr-plus">+</button></label>
        <label>Capo<input type="number" min={0} max={12} value={capo} data-testid="sheet-capo" className="num" onChange={(e) => setCapo(Math.max(0, Math.min(12, Number(e.target.value) || 0)))} /></label>
        {capo > 0 && <label title="เปิด = แสดงรูปมือที่ต้องกด (เสียงจริงอยู่ที่ capo)"><input type="checkbox" checked={shapes} onChange={(e) => setShapes(e.target.checked)} /> แสดงรูปมือ (ติด capo {capo})</label>}
        <label><input type="checkbox" checked={dedupe} onChange={(e) => setDedupe(e.target.checked)} /> ซ่อนคอร์ดซ้ำ</label>
        <label>ขนาด<input type="range" min={12} max={26} value={size} onChange={(e) => setSize(+e.target.value)} /></label>
        <span className="muted small">คลิกคอร์ด = ดูทรง · ดับเบิลคลิก = แก้ (ว่าง = ลบ) · คลิกแถว = ไปที่ตำแหน่งนั้น</span>
      </div>
      <SongPanels />
      {!hasData ? <p className="muted">ยังไม่มีคอร์ด — วิเคราะห์เพลงใหม่อีกครั้งเพื่อสร้างคอร์ดและท่อน (ต้องมี BTC ติดตั้งแล้ว)</p> : (
        <div className="sheet" style={{ fontSize: size }}>
          {sheet.map((sec, si) => (
            <section key={si} className="sheetsec">
              <h3>{sec.section ? sec.section.label : 'บทนำ'}{sec.section && !sec.section.auto && <span className="muted"> ✎</span>}</h3>
              {sec.rows.map((row, ri) => {
                const on = active?.section === si && active.row === ri
                return (
                  <div key={ri} className={`sheetrow ${row.kind} ${on ? 'on' : ''}`} data-row={`${si}-${ri}`} data-testid="sheet-row"
                    onClick={() => tr.seek(Math.max(0, row.start - 0.1))}>
                    {row.kind === 'instr' ? (
                      <div className="instr">{row.chords.map((c, i) => chord(c, `c${i}`))}<span className="muted small"> ♪</span></div>
                    ) : (
                      <div className="lyric">
                        {row.slots.map((s, i) => (
                          <Fragment key={i}>
                            <span className="slot" data-active={on && tr.getTime() >= s.start && tr.getTime() < s.end ? '1' : undefined}>
                              <span className="chords">{s.chords.map((c, k) => chord(c, `${i}-${k}`))}</span>
                              <span className="word">{s.text}</span>
                            </span>
                            {!NOSPACE(s.text) && ' '}
                          </Fragment>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </section>
          ))}
        </div>
      )}
      {pop && (
        <div className="popover" style={{ left: Math.min(pop.x, window.innerWidth - 130), top: pop.y + 6 }} onClick={(e) => e.stopPropagation()}>
          <ChordDiagram symbol={pop.symbol} />
          {capo > 0 && shapes && <div className="muted small">เสียงจริง {transposeChord(pop.symbol, capo, flats)}</div>}
          <div className="muted small">{spellChord(pop.symbol, flats)}</div>
        </div>
      )}
    </div>
  )
}
