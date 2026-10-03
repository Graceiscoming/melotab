import { useEffect, useMemo, useRef, useState } from 'react'
import { getTransport } from '../../audio/instance'
import { detectPitch, hzToMidi } from '../../practice/pitch'
import { PracticeScorer, type NoteResult } from '../../practice/scorer'
import { TUNINGS, techniqueMark } from '../../tab/ops'
import { noteName } from '../../theory/notes'
import { useStore } from '../../store/store'
import type { TabEvent } from '../../types'

const FRETS = 22
const W = 1180
const LEFT = 40
const FW = (W - LEFT - 20) / FRETS
const SG = 34
const H = 5 * SG + 70
const MARKS = [3, 5, 7, 9, 12, 15, 17, 19, 21]
const COLOR: Record<NoteResult, string> = { hit: '#4ade80', miss: '#f87171', octave: '#fbbf24' }

/** โหมดซ้อม: คอกีตาร์ใหญ่แสดงโน้ตปัจจุบัน/โน้ตถัดไปวิ่งตามเพลง + (ถ้าเปิดไมค์) ฟังว่าเล่นถูกไหม ให้คะแนนต่อโน้ต */
export function PracticeView() {
  const { tab, tabSettings: S, song } = useStore()
  const tr = getTransport()
  const events = useMemo(() => (tab?.events ?? []).filter((e) => e.string !== null && e.fret !== null).sort((a, b) => a.start - b.start), [tab])
  const [curIdx, setCurIdx] = useState(-1)
  const [mic, setMic] = useState<'off' | 'starting' | 'on'>('off')
  const [micErr, setMicErr] = useState('')
  const [heard, setHeard] = useState<{ name: string; cents: number } | null>(null)
  const [score, setScore] = useState({ hit: 0, miss: 0, octave: 0, total: 0, pct: 0 })
  const [results, setResults] = useState<Map<string, NoteResult>>(new Map())
  const scorer = useRef<PracticeScorer | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const micCtx = useRef<AudioContext | null>(null)
  const timer = useRef<number | null>(null)
  const lastT = useRef(0)

  useEffect(() => { scorer.current = new PracticeScorer(events) }, [events])

  // เลื่อนตามเวลาเพลง: หาโน้ตปัจจุบัน (ตัวล่าสุดที่เริ่มแล้ว)
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const t = tr.getTime()
      let lo = 0
      let hi = events.length
      while (lo < hi) { const m = (lo + hi) >> 1; if (events[m].start <= t) lo = m + 1; else hi = m }
      setCurIdx((p) => (p === lo - 1 ? p : lo - 1))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [events, tr])

  async function startMic() {
    setMic('starting'); setMicErr('')
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } })
      stream.current = s
      const ctx = new AudioContext()
      micCtx.current = ctx
      const an = ctx.createAnalyser()
      an.fftSize = 4096
      ctx.createMediaStreamSource(s).connect(an)
      const buf = new Float32Array(an.fftSize)
      scorer.current?.seek(tr.getTime())
      timer.current = window.setInterval(() => {
        an.getFloatTimeDomainData(buf)
        const p = detectPitch(buf, ctx.sampleRate)
        const t = tr.getTime()
        if (Math.abs(t - lastT.current) > 0.5 || t < lastT.current) scorer.current?.seek(t) // seek/loop: เริ่มตัดสินใหม่
        lastT.current = t
        if (p) {
          const m = hzToMidi(p.hz)
          setHeard({ name: noteName(Math.round(m)), cents: Math.round((m - Math.round(m)) * 100) })
        } else setHeard(null)
        if (tr.playing) {
          scorer.current?.update(t, p ? hzToMidi(p.hz) : null)
          setScore(scorer.current!.summary())
          setResults(new Map(scorer.current!.results))
        }
      }, 40)
      setMic('on')
    } catch (e) {
      setMic('off')
      setMicErr(`เปิดไมค์ไม่สำเร็จ: ${e instanceof Error ? e.message : e}`)
    }
  }
  function stopMic() {
    if (timer.current !== null) clearInterval(timer.current)
    timer.current = null
    stream.current?.getTracks().forEach((t) => t.stop())
    void micCtx.current?.close()
    stream.current = null; micCtx.current = null
    setMic('off'); setHeard(null)
  }
  useEffect(() => () => stopMic(), []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!tab || !song) return <div className="practice muted">ยังไม่มีแทป — เปิดโหมด Guitar Tab เพื่อสร้างก่อน</div>
  const tuning = TUNINGS[S.tuning] ?? TUNINGS.standard
  const x = (f: number) => LEFT + (f === 0 ? -FW / 2 + 6 : (f - 0.5) * FW)
  const y = (s: number) => 30 + (s - 1) * SG
  const cur = curIdx >= 0 ? events[curIdx] : null
  const upcoming: TabEvent[] = events.slice(curIdx + 1, curIdx + 4)
  const mark = cur ? techniqueMark(cur.techniques) : ''

  return (
    <div className="practice" data-testid="practice">
      <div className="pr-top">
        <div className="pr-now" data-testid="pr-now">
          {cur ? <><span className="pr-note">{noteName(cur.pitch, song.key)}</span> <span className="muted">สาย {cur.string} · ช่อง {cur.fret}{mark ? ` ${mark}` : ''}</span></> : <span className="muted">กด ▶ เล่น แล้วดูตำแหน่งนิ้ววิ่งบนคอ</span>}
        </div>
        <span className="spacer" />
        {mic === 'on' ? <button onClick={stopMic} data-testid="mic-stop">⏹ ปิดไมค์</button> : <button onClick={() => void startMic()} disabled={mic === 'starting'} data-testid="mic-start">🎤 เปิดไมค์ (ให้คะแนน)</button>}
      </div>
      <svg width={W} height={H} className="bigfret" data-testid="bigfret">
        {Array.from({ length: FRETS + 1 }, (_, f) => <line key={f} x1={LEFT + f * FW} x2={LEFT + f * FW} y1={y(1) - 12} y2={y(6) + 12} stroke={f === 0 ? '#c9cfdd' : '#3b4252'} strokeWidth={f === 0 ? 5 : 1.5} />)}
        {[1, 2, 3, 4, 5, 6].map((s) => <line key={s} x1={LEFT} x2={LEFT + FRETS * FW} y1={y(s)} y2={y(s)} stroke="#8a93a8" strokeWidth={1 + (s - 1) * 0.5} />)}
        {[1, 2, 3, 4, 5, 6].map((s) => <text key={s} x={14} y={y(s) + 5} fontSize={14} fill="#8a93a8" textAnchor="middle">{noteName(tuning[6 - s] + S.capo).replace(/\d/g, '')}</text>)}
        {MARKS.map((f) => <text key={f} x={LEFT + (f - 0.5) * FW} y={H - 14} fontSize={13} fill="#6f7a92" textAnchor="middle">{f}</text>)}
        {[...results.entries()].slice(-12).map(([id, r]) => {
          const e = events.find((q) => q.id === id)
          return e ? <circle key={id} cx={x(e.fret!)} cy={y(e.string!)} r={7} fill={COLOR[r]} opacity={0.35} /> : null
        })}
        {upcoming.map((e, i) => (
          <g key={e.id} opacity={0.75 - i * 0.2}>
            <circle cx={x(e.fret!)} cy={y(e.string!)} r={13} fill="none" stroke="#5aa9ff" strokeWidth={2} strokeDasharray="4 3" />
            <text x={x(e.fret!)} y={y(e.string!) + 5} fontSize={14} fill="#5aa9ff" textAnchor="middle">{i + 1}</text>
          </g>
        ))}
        {cur && (
          <g data-testid="bigfret-cur" data-id={cur.id}>
            <circle cx={x(cur.fret!)} cy={y(cur.string!)} r={17} fill="#ff5c7a" opacity={0.25}><animate attributeName="r" values="15;22;15" dur="0.9s" repeatCount="indefinite" /></circle>
            <circle cx={x(cur.fret!)} cy={y(cur.string!)} r={13} fill="#ff5c7a" />
            <text x={x(cur.fret!)} y={y(cur.string!) + 6} fontSize={16} fontWeight={700} fill="#fff" textAnchor="middle">{cur.fret}</text>
          </g>
        )}
      </svg>
      <div className="pr-mic" data-testid="pr-mic">
        {micErr && <span className="err small">{micErr}</span>}
        {mic === 'on' && (
          <>
            <span>ได้ยิน: <b data-testid="pr-heard">{heard ? `${heard.name} (${heard.cents > 0 ? '+' : ''}${heard.cents}¢)` : '—'}</b></span>
            <span>คะแนน <b data-testid="pr-score">{score.pct}%</b> <span className="muted">ถูก {score.hit} · ผิด {score.miss} · คนละ octave {score.octave} / {score.total} โน้ต</span></span>
          </>
        )}
        {mic === 'off' && !micErr && <span className="muted small">ใช้หูฟังเพื่อไม่ให้เสียงเพลงเข้าไมค์ · เล่นตามแทปแล้วระบบเทียบ pitch กับโน้ตที่ควรเล่น (±50 cents) — เป็นการเทียบ pitch เท่านั้น ไม่ตรวจจังหวะละเอียด</span>}
      </div>
    </div>
  )
}
