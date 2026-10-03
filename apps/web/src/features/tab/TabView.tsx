import { useEffect, useMemo, useRef, useState } from 'react'
import { getTransport } from '../../audio/instance'
import { useStore } from '../../store/store'
import { beatToTime } from '../../theory/rhythm'
import { LAYOUT, layoutTab, timeToPos, type TabLayout } from '../../tab/layout'
import { moveString, removeNote, setFret, shiftFret, toggleLock, toggleTechnique, techniqueMark, type State as EditState, type TechKey } from '../../tab/ops'
import type { TabEvent } from '../../types'

const LINE_GAP = 16
const TOP = 44
const SYS_H = 150
const STRINGS = [1, 2, 3, 4, 5, 6]
const yOf = (s: number) => TOP + (s - 1) * LINE_GAP

const TECH_KEYS: Record<string, TechKey> = { KeyH: 'hammer', KeyP: 'pull', KeyS: 'slide', KeyB: 'bend', KeyR: 'release', KeyV: 'vibrato', KeyG: 'grace' }

/** สีความยาก: เขียว → เหลือง → แดง (ใช้กับ heatmap) */
export const heatColor = (d: number): string => (d < 0.35 ? '#2f7d4f' : d < 0.65 ? '#8a7a22' : '#9c3340')

/** ตำแหน่ง x ในบรรทัด → เวลา (วินาที) เพื่อคลิกแล้ว seek */
function xToTime(layout: TabLayout, beats: { time: number }[], system: number, x: number): number | null {
  const sys = layout.systems[system]
  if (!sys) return null
  const bar = sys.bars.find((b) => x >= b.x && x < b.x + b.width) ?? sys.bars[sys.bars.length - 1]
  const frac = Math.max(0, Math.min(1, (x - bar.x - LAYOUT.barPad) / (bar.width - LAYOUT.barPad * 2)))
  return beatToTime(beats as never, bar.startBeat + frac * bar.beats)
}

export function TabView() {
  const { song, tab, tabSel, selectedNoteId, locked, techniques, view } = useStore()
  const wrap = useRef<HTMLDivElement>(null)
  const playLines = useRef<(SVGLineElement | null)[]>([])
  const [width, setWidth] = useState(1000)
  const tr = getTransport()
  const digitBuf = useRef<{ v: number; t: number } | null>(null)

  useEffect(() => {
    const el = wrap.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(Math.max(500, el.clientWidth - 24)))
    ro.observe(el)
    setWidth(Math.max(500, el.clientWidth - 24))
    return () => ro.disconnect()
  }, [])

  const events = tab?.events ?? []
  const beats = song?.beats ?? []
  const layout = useMemo(() => layoutTab(events, beats, width, song?.source.duration ?? 0), [events, beats, width, song?.source.duration])
  const byId = useMemo(() => new Map(events.map((e) => [e.id, e])), [events])

  // playhead + เลื่อนตามเพลง (อัปเดตผ่าน ref ไม่ re-render ทุกเฟรม)
  useEffect(() => {
    let raf = 0
    let lastSys = -1
    const loop = () => {
      const p = timeToPos(layout, beats, tr.getTime())
      playLines.current.forEach((ln, i) => {
        if (!ln) return
        if (p && p.system === i) {
          ln.setAttribute('x1', String(p.x))
          ln.setAttribute('x2', String(p.x))
          ln.style.visibility = 'visible'
        } else ln.style.visibility = 'hidden'
      })
      if (p && tr.playing && useStore.getState().view.follow && p.system !== lastSys && wrap.current) {
        wrap.current.scrollTo({ top: Math.max(0, p.system * SYS_H - 40), behavior: 'smooth' })
      }
      if (p) lastSys = p.system
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [layout, beats, tr])

  // คีย์บอร์ด (ทำงานเมื่อเปิดโหมดแทป)
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (view.mode !== 'tab') return
      const el = e.target as HTMLElement
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) return
      if (e.ctrlKey || e.metaKey) return
      const st = useStore.getState()
      const settings = st.tabSettings
      const key = st.song?.key ?? null
      const sel = (st.tabSel.length ? st.tabSel : st.selectedNoteId ? [st.selectedNoteId] : [])
        .map((id) => st.tab?.events.find((x) => x.note_id === id)).filter((x): x is TabEvent => !!x)
      const primary = st.selectedNoteId ? st.tab?.events.find((x) => x.note_id === st.selectedNoteId) : undefined
      const order = [...(st.tab?.events ?? [])].filter((x) => x.fret !== null).sort((a, b) => a.start - b.start)

      if (e.code === 'ArrowLeft' || e.code === 'ArrowRight') {
        e.preventDefault()
        const i = primary ? order.findIndex((x) => x.id === primary.id) : -1
        const next = order[Math.max(0, Math.min(order.length - 1, i + (e.code === 'ArrowRight' ? 1 : -1)))]
        if (next) { st.selectNote(next.note_id); tr.audition(next.pitch, 0.3) }
        return
      }
      if (sel.length === 0) return
      /** ใช้การแก้กับทุกตัวที่เลือก (ตัวไหนทำไม่ได้ก็ข้าม; ถ้าไม่มีตัวไหนเปลี่ยนเลยจะไม่สร้าง undo step) */
      const apply = (fn: (s: EditState, ev: TabEvent) => EditState | null) =>
        st.editState((s) => {
          let cur = s
          let changed = false
          for (const ev of sel) {
            const r = fn(cur, ev)
            if (r) { cur = r; changed = true }
          }
          return changed ? cur : null
        })
      if (e.code === 'ArrowUp' || e.code === 'ArrowDown') {
        e.preventDefault()
        if (e.altKey) {
          apply((s, ev) => shiftFret(s, ev, e.code === 'ArrowUp' ? 1 : -1, settings, key))
        } else {
          // ↑ = ขึ้นสายบาง (เลขสายลด) ↓ = ลงสายหนา (เลขสายเพิ่ม) โดยรักษา pitch เดิม
          apply((s, ev) => moveString(s, ev, e.code === 'ArrowUp' ? -1 : 1, settings))
        }
        const after = useStore.getState().tab?.events.find((x) => x.note_id === sel[0].note_id)
        if (after) tr.audition(after.pitch, 0.3)
      } else if (e.code === 'Delete' || e.code === 'Backspace') {
        e.preventDefault()
        apply((s, ev) => removeNote(s, ev.note_id))
        st.selectNote(null)
      } else if (e.code === 'KeyL') {
        apply((s, ev) => toggleLock(s, ev))
      } else if (TECH_KEYS[e.code]) {
        apply((s, ev) => toggleTechnique(s, ev.note_id, TECH_KEYS[e.code]))
      } else if (/^Digit\d$/.test(e.code) && primary) {
        e.preventDefault()
        const d = Number(e.code.slice(5))
        const now = Date.now()
        const buf = digitBuf.current
        const two = buf && now - buf.t < 800 ? buf.v * 10 + d : null
        const fret = two !== null && two <= settings.max_fret ? two : d
        digitBuf.current = { v: fret, t: now }
        st.editState((s) => setFret(s, primary, fret, settings, key))
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [view.mode, tr])

  if (!song) return null
  if (!tab) {
    return (
      <div className="tabempty" ref={wrap} data-testid="tab-empty">
        <p>ยังไม่มีแทป — ตั้งค่าที่แผงด้านขวาแล้วกด <b>สร้างแทป</b></p>
      </div>
    )
  }

  const selSet = new Set(tabSel)
  const warnColor = (e: TabEvent) =>
    e.warnings.includes('hard_shift') || e.warnings.includes('stretch') ? '#ff6b81'
      : e.warnings.includes('out_of_block') || e.warnings.includes('octave_shifted') ? '#ffa94d' : '#e8eaf0'

  return (
    <div className="tabview" ref={wrap} data-testid="tabview">
      {layout.systems.map((sys) => (
        <svg key={sys.index} width={Math.max(sys.width + 20, width)} height={SYS_H} className="tabsys" data-system={sys.index}
          onClick={(ev) => {
            if ((ev.target as Element).closest('[data-ev]')) return
            const r = (ev.currentTarget as SVGSVGElement).getBoundingClientRect()
            const t = xToTime(layout, beats, sys.index, ev.clientX - r.left)
            if (t !== null) tr.seek(Math.max(0, t))
          }}>
          {/* เส้นสาย + เลขสาย */}
          {STRINGS.map((s) => <line key={s} x1={LAYOUT.leftMargin - 6} x2={sys.width} y1={yOf(s)} y2={yOf(s)} stroke="#3b4252" strokeWidth={1} />)}
          <text x={4} y={yOf(3.5) + 4} fontSize={12} fill="#8b93a7" fontWeight={700}>TAB</text>
          {sys.bars.map((b) => (
            <g key={b.index}>
              <line x1={b.x} x2={b.x} y1={yOf(1)} y2={yOf(6)} stroke="#5b6478" strokeWidth={1.5} />
              <text x={b.x + 3} y={TOP - 12} fontSize={10} fill="#6f7a92">{b.index + 1}</text>
            </g>
          ))}
          <line x1={sys.width} x2={sys.width} y1={yOf(1)} y2={yOf(6)} stroke="#5b6478" strokeWidth={1.5} />
          {/* เลขช่อง */}
          {sys.bars.flatMap((b) => b.events).map(({ id, x }) => {
            const e = byId.get(id)
            if (!e || e.fret === null || e.string === null) return null
            const y = yOf(e.string)
            const selected = selSet.has(e.note_id)
            const mark = techniqueMark(techniques[e.note_id] ?? e.techniques)
            const label = String(e.fret)
            const w = label.length * 8 + 8 + (mark ? 6 : 0)
            return (
              <g key={id} data-ev={e.note_id} data-testid="tab-event" data-string={e.string} data-fret={e.fret}
                style={{ cursor: 'pointer' }}
                onClick={(ev) => {
                  ev.stopPropagation()
                  if (ev.shiftKey) useStore.getState().toggleTabSel(e.note_id)
                  else useStore.getState().selectNote(e.note_id)
                  tr.audition(e.pitch, 0.3)
                }}>
                <rect x={x - w / 2} y={y - 9} width={w} height={18} rx={4}
                  fill={view.heatmap ? heatColor(e.difficulty) : '#14161b'}
                  stroke={selected ? '#5aa9ff' : selectedNoteId === e.note_id ? '#fff' : 'transparent'} strokeWidth={selected ? 2 : 1} />
                <text x={x - (mark ? 3 : 0)} y={y + 4} textAnchor="middle" fontSize={13} fontWeight={600} fill={warnColor(e)}>{label}</text>
                {mark && <text x={x + label.length * 4 + 3} y={y - 1} textAnchor="start" fontSize={10} fill="#ffd666">{mark}</text>}
                {(locked[e.note_id] || e.locked) && <circle cx={x + w / 2 - 2} cy={y - 8} r={3} fill="#5aa9ff" />}
                {e.warnings.includes('octave_shifted') && <text x={x - w / 2} y={y - 10} fontSize={9} fill="#ffa94d">8va</text>}
              </g>
            )
          })}
          <line ref={(el) => { playLines.current[sys.index] = el }} y1={yOf(1) - 14} y2={yOf(6) + 12} stroke="#ff5c7a" strokeWidth={2} style={{ visibility: 'hidden' }} />
        </svg>
      ))}
      {tab.summary.unplayable > 0 && (
        <p className="warn">⚠ {tab.summary.unplayable} โน้ตเล่นไม่ได้ในจูนนิ่ง/capo นี้ (ไม่แสดงในแทป) — ลองเปลี่ยนคีย์/capo หรือ octave</p>
      )}
    </div>
  )
}
