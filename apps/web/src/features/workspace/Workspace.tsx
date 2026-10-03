import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { getTransport } from '../../audio/instance'
import type { TrackName } from '../../audio/transport'
import { mergeNext, movePitch, needsReview, nextReview, remove, splitAt } from '../../store/edits'
import { useStore } from '../../store/store'
import { ExportDialog } from '../export/ExportDialog'
import { PracticeView } from '../practice/PracticeView'
import { PianoRoll } from '../pianoroll/PianoRoll'
import { ChordSheet } from '../sheet/ChordSheet'
import { TabPanel } from '../tab/TabPanel'
import { TabView } from '../tab/TabView'

const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`
const TRACK_LABEL: Record<TrackName, string> = {
  mix: 'เพลงเต็ม', vocals: 'เสียงร้อง', instrumental: 'ดนตรี (ไม่มีร้อง)', lead: 'เสียงร้องนำ', backing: 'เสียงประสาน', lead_dry: 'ร้องนำ (ไม่มี reverb)',
}
const SAVE_LABEL = { saved: '✓ บันทึกแล้ว', dirty: '● มีการแก้ไข', saving: '… กำลังบันทึก', error: '✗ บันทึกไม่สำเร็จ' } as const

export function Workspace() {
  const { song, currentId, view, setView, selectedNoteId, closeProject, setError, saveState, past, future, tab, tabSettings } = useStore()
  const tr = getTransport()
  const [playing, setPlaying] = useState(false)
  const [track, setTrack] = useState<TrackName>('mix')
  const [synth, setSynth] = useState(false)
  const [click, setClick] = useState(false)
  const [split, setSplit] = useState(false)
  const [ready, setReady] = useState(false)
  const [rate, setRateUi] = useState(1)
  const [countIn, setCountIn] = useState(0)
  const [stretching, setStretching] = useState(false)
  const [loopAB, setLoopAB] = useState<{ a: number | null; b: number | null }>({ a: null, b: null })
  const [exporting, setExporting] = useState(false)
  const [panel, setPanel] = useState<'' | 'sens' | 'history'>('')
  const timeEl = useRef<HTMLSpanElement>(null)

  const tracks: TrackName[] = ['mix', 'vocals', 'instrumental',
    ...(song?.meta.karaoke ? (['lead', 'backing'] as TrackName[]) : []),
    ...(song?.meta.dereverb ? (['lead_dry'] as TrackName[]) : [])]

  // โหลดเสียงเมื่อเปิดโปรเจกต์ (ไม่โหลดซ้ำเมื่อโน้ตถูกแก้)
  useEffect(() => {
    if (!currentId) return
    tr.clearTracks()
    setReady(false)
    setPlaying(false)
    tr.onEnded = () => setPlaying(false)
    tr.loadTrack('mix', api.audioUrl(currentId, 'mix')).then(() => { setTrack('mix'); setReady(true) })
      .catch((e) => setError(`โหลดเสียงไม่สำเร็จ: ${e instanceof Error ? e.message : e}`))
    return () => { tr.pause() }
  }, [currentId]) // eslint-disable-line react-hooks/exhaustive-deps

  // ส่งโน้ต/beat ล่าสุดให้ transport (synth + metronome ใช้ข้อมูลที่แก้แล้วทันที)
  useEffect(() => { if (song) tr.setSong(song.notes, song.beats) }, [song, tr])
  useEffect(() => { tr.synthOn = synth }, [synth, tr])
  useEffect(() => { tr.noteTranspose = view.mode === 'tab' ? tabSettings.transpose : 0 }, [view.mode, tabSettings.transpose, tr])
  // เข้าโหมดแทปครั้งแรกโดยยังไม่มีแทป → สร้างให้เลย
  useEffect(() => { if ((view.mode === 'tab' || view.mode === 'practice') && !tab && song) void useStore.getState().regenerateTab() }, [view.mode]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { tr.clickOn = click }, [click, tr])
  useEffect(() => { tr.setSplit(split) }, [split, tr])
  useEffect(() => { tr.countIn = countIn }, [countIn, tr])
  useEffect(() => { tr.loop = loopAB.a !== null && loopAB.b !== null && loopAB.b > loopAB.a ? { a: loopAB.a, b: loopAB.b } : null }, [loopAB, tr])
  useEffect(() => { setRateUi(1); setLoopAB({ a: null, b: null }); tr.rate = 1 }, [currentId, tr])

  useEffect(() => {
    let raf = 0
    const loop = () => {
      if (timeEl.current) timeEl.current.textContent = `${fmt(tr.getTime())} / ${fmt(tr.duration || song?.source.duration || 0)}`
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [tr, song?.source.duration])

  function toggle() {
    if (!ready) return
    if (tr.playing) { tr.pause(); setPlaying(false) } else { void tr.play(tr.loop && (tr.getTime() < tr.loop.a || tr.getTime() >= tr.loop.b) ? tr.loop.a : undefined, true); setPlaying(true) }
  }

  async function changeRate(r: number) {
    setRateUi(r)
    try { await tr.setRate(r, setStretching) } catch (e) { setError(`ปรับความเร็วไม่สำเร็จ: ${e instanceof Error ? e.message : e}`) }
  }

  function jumpToReview() {
    const st = useStore.getState()
    if (!st.song) return
    const n = nextReview(st.song.notes, tr.getTime(), st.selectedNoteId)
    if (!n) return
    st.selectNote(n.id)
    setView({ follow: false })
    st.requestFocus(n.start)
    tr.seek(Math.max(0, n.start - 0.5))
    tr.audition(n.midi, Math.min(0.8, n.end - n.start))
  }

  // ปุ่มลัด
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) return
      const st = useStore.getState()
      const key = st.song?.key ?? null
      const id = st.selectedNoteId
      const mod = e.ctrlKey || e.metaKey
      if (e.code === 'Space' && el.tagName !== 'BUTTON') { e.preventDefault(); toggle(); return }
      if (mod && e.code === 'KeyZ') { e.preventDefault(); if (e.shiftKey) st.redo(); else st.undo(); return }
      if (mod && e.code === 'KeyY') { e.preventDefault(); st.redo(); return }
      if (e.code === 'KeyN') { jumpToReview(); return }
      if (st.view.mode !== 'roll') return   // ปุ่มที่เหลือเป็นของตัวแก้ไขแทป (TabView) / Chord Sheet
      if (!id) return
      if (e.code === 'Delete' || e.code === 'Backspace') { e.preventDefault(); st.editNotes((ns) => remove(ns, id), null) }
      else if (e.code === 'ArrowUp' || e.code === 'ArrowDown') {
        e.preventDefault()
        const d = (e.code === 'ArrowUp' ? 1 : -1) * (e.shiftKey ? 12 : 1)
        st.editNotes((ns) => movePitch(ns, id, d, key))
        const n = useStore.getState().song?.notes.find((x) => x.id === id)
        if (n) tr.audition(n.midi, 0.3)
      } else if (e.code === 'KeyS') st.editNotes((ns) => splitAt(ns, id, tr.getTime(), key))
      else if (e.code === 'KeyM') st.editNotes((ns) => mergeNext(ns, id, key))
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  })

  // เตือนก่อนปิดแท็บถ้ายังมีงานที่ยังไม่ได้บันทึก
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => { if (useStore.getState().saveState !== 'saved') { e.preventDefault(); void useStore.getState().saveNow() } }
    window.addEventListener('beforeunload', h)
    return () => window.removeEventListener('beforeunload', h)
  }, [])

  async function changeTrack(t: TrackName) {
    if (!currentId) return
    try { await tr.loadTrack(t, api.audioUrl(currentId, t)); setTrack(t) } catch (e) { setError(String(e)) }
  }

  if (!song) return null
  const sel = song.notes.find((n) => n.id === selectedNoteId)
  const review = needsReview(song.notes).length
  const edited = song.notes.filter((n) => n.edited).length

  return (
    <div className="workspace">
      <div className="infobar">
        <button onClick={closeProject} data-testid="back">← โปรเจกต์</button>
        <b className="title">{song.source.title}</b>
        <span>คีย์ <b data-testid="key">{song.key ? `${song.key.tonic} ${song.key.mode}` : '—'}</b></span>
        <span>BPM <b data-testid="bpm">{song.tempo.bpm ?? '—'}</b>{song.tempo.unstable && <span className="warn" title="Beat This! สลับ tempo ครึ่ง/เท่าตัวในบางช่วง"> ⚠ tempo ไม่นิ่ง</span>}</span>
        <span>{song.time_signature ? `${song.time_signature.num}/${song.time_signature.den}` : ''}</span>
        {typeof song.tuning_offset_cents === 'number' && <span title="ประเมินจาก f0 เทียบ A=440 (หยาบ ±~10 cents)">tuning <b data-testid="tuning">{song.tuning_offset_cents > 0 ? '+' : ''}{song.tuning_offset_cents}</b>¢</span>}
        <span><b data-testid="notecount">{song.notes.length}</b> โน้ต{edited > 0 && <span className="muted"> (แก้ {edited})</span>}</span>
        <button className={review ? 'warnbtn' : ''} onClick={jumpToReview} disabled={review === 0} data-testid="review"
          title="กระโดดไปโน้ตที่ความมั่นใจต่ำ/สงสัยผิด octave ตัวถัดไป (ปุ่ม N)">{review} ควรตรวจ ▸</button>
        <span className="spacer" />
        <button onClick={() => useStore.getState().undo()} disabled={past.length === 0} data-testid="undo" title="Ctrl+Z">↶</button>
        <button onClick={() => useStore.getState().redo()} disabled={future.length === 0} data-testid="redo" title="Ctrl+Y">↷</button>
        <span className={saveState === 'error' ? 'err' : 'muted'} data-testid="savestate">{SAVE_LABEL[saveState]}</span>
        <button onClick={() => setPanel(panel === 'sens' ? '' : 'sens')}>ความละเอียดโน้ต</button>
        <button onClick={() => setPanel(panel === 'history' ? '' : 'history')}>เวอร์ชันก่อนหน้า</button>
        <button className="primary" onClick={() => setExporting(true)} data-testid="export-btn">Export</button>
      </div>

      {exporting && <ExportDialog onClose={() => setExporting(false)} />}
      {panel === 'sens' && <SensitivityPanel onClose={() => setPanel('')} />}
      {panel === 'history' && <HistoryPanel onClose={() => setPanel('')} />}

      <div className="modetabs">
        <button className={view.mode === 'roll' ? 'on' : ''} onClick={() => setView({ mode: 'roll' })} data-testid="mode-roll">Piano Roll</button>
        <button className={view.mode === 'tab' ? 'on' : ''} onClick={() => setView({ mode: 'tab' })} data-testid="mode-tab">Guitar Tab</button>
        <button className={view.mode === 'sheet' ? 'on' : ''} onClick={() => setView({ mode: 'sheet' })} data-testid="mode-sheet">Chord Sheet</button>
        <button className={view.mode === 'practice' ? 'on' : ''} onClick={() => setView({ mode: 'practice' })} data-testid="mode-practice">ซ้อม</button>
        {view.mode === 'tab' && <label className="heat"><input type="checkbox" checked={view.heatmap} onChange={(e) => setView({ heatmap: e.target.checked })} data-testid="heatmap" /> heatmap ความยาก (เขียว/เหลือง/แดง)</label>}
      </div>
      {view.mode === 'roll' ? <PianoRoll /> : view.mode === 'sheet' ? <ChordSheet /> : view.mode === 'practice' ? <PracticeView /> : <div className="tabarea"><TabView /><TabPanel /></div>}

      <div className="transport">
        <button className="play" onClick={toggle} disabled={!ready} data-testid="play">{playing ? '⏸ หยุด' : '▶ เล่น'}</button>
        <span ref={timeEl} className="time" data-testid="time">0:00.0</span>
        <label>เสียง <select value={track} onChange={(e) => void changeTrack(e.target.value as TrackName)}>
          {tracks.map((t) => <option key={t} value={t}>{TRACK_LABEL[t]}</option>)}</select></label>
        <label><input type="checkbox" checked={synth} onChange={(e) => setSynth(e.target.checked)} /> เสียงโน้ต (synth)</label>
        <label title="เพลงออกหูซ้าย / synth ออกหูขวา เพื่อฟังเทียบว่าโน้ตตรงไหม"><input type="checkbox" checked={split} onChange={(e) => setSplit(e.target.checked)} /> ฟังเทียบ ซ้าย/ขวา</label>
        <label><input type="checkbox" checked={click} onChange={(e) => setClick(e.target.checked)} /> Metronome</label>
        <label title="นับจังหวะก่อนเริ่มเล่น">นับ <select value={countIn} onChange={(e) => setCountIn(+e.target.value)} data-testid="countin">
          {[0, 1, 2, 4].map((n) => <option key={n} value={n}>{n === 0 ? 'ปิด' : `${n} จังหวะ`}</option>)}</select></label>
        <label title="ช้าลงโดยไม่เพี้ยนเสียง (ครั้งแรกต้องประมวลผลสักครู่)">ความเร็ว <select value={rate} onChange={(e) => void changeRate(+e.target.value)} disabled={!ready || stretching} data-testid="rate">
          {[0.5, 0.6, 0.75, 0.9, 1, 1.1].map((r) => <option key={r} value={r}>{Math.round(r * 100)}%</option>)}</select>{stretching && <span className="muted"> … ประมวลผล</span>}</label>
        <span className="loopctl" title="วนซ้ำช่วง A–B (ซ้อมท่อนที่ยาก)">
          <button onClick={() => setLoopAB((l) => ({ ...l, a: tr.getTime() }))} data-testid="loop-a">A{loopAB.a !== null ? ` ${loopAB.a.toFixed(1)}` : ''}</button>
          <button onClick={() => setLoopAB((l) => ({ ...l, b: tr.getTime() }))} data-testid="loop-b">B{loopAB.b !== null ? ` ${loopAB.b.toFixed(1)}` : ''}</button>
          {(loopAB.a !== null || loopAB.b !== null) && <button onClick={() => setLoopAB({ a: null, b: null })}>ล้าง loop</button>}
        </span>
        <span className="spacer" />
        <label><input type="checkbox" checked={view.snap} onChange={(e) => setView({ snap: e.target.checked })} /> snap ตาม beat</label>
        <label><input type="checkbox" checked={view.follow} onChange={(e) => setView({ follow: e.target.checked })} /> ตามเพลง</label>
        <label><input type="checkbox" checked={view.showF0} onChange={(e) => setView({ showF0: e.target.checked })} /> เส้น pitch จริง</label>
        <label><input type="checkbox" checked={view.highlightKey} onChange={(e) => setView({ highlightKey: e.target.checked })} /> ไฮไลต์คีย์</label>
        <label>ซูม <input type="range" min={15} max={400} value={view.pxPerSec} onChange={(e) => setView({ pxPerSec: +e.target.value })} /></label>
      </div>

      <div className="notepanel" data-testid="notepanel">
        {sel ? (
          <>
            <b>{sel.name}</b> · MIDI {sel.midi} · {sel.freq} Hz · {sel.start.toFixed(2)}–{sel.end.toFixed(2)} s
            {sel.dur_beats !== undefined && <> · {sel.dur_beats} beat</>}
            {sel.start_beat_q !== undefined && <span title="ปัดเข้ากริด 1/16 โดยเก็บเวลาจริงไว้"> · quantized: beat {sel.start_beat_q} ยาว {sel.dur_beats_q}</span>}
            · cents {sel.cents_offset ?? '—'} · ความมั่นใจ {(sel.confidence * 100).toFixed(0)}%
            {sel.octave_fixed && <span className="warn"> · ⚠ ระบบย้าย octave ให้ตาม f0 (ตรวจด้วย)</span>}
            {sel.octave_suspect && <span className="warn"> · ⚠ สงสัยผิด octave</span>}
            {sel.edited && <span className="muted"> · แก้โดยคุณ</span>}
          </>
        ) : (
          <span className="muted">คลิกโน้ตเพื่อดู/แก้ · ลากขึ้นลง = เปลี่ยน pitch · ลากขอบ = ปรับความยาว · ดับเบิลคลิกที่ว่าง = เพิ่มโน้ต · ↑↓ (Shift = octave) · Delete ลบ · S แบ่งที่ playhead · M รวมกับตัวถัดไป · N ข้ามไปโน้ตที่ควรตรวจ · Ctrl+Z/Y</span>
        )}
      </div>
    </div>
  )
}

function SensitivityPanel({ onClose }: { onClose: () => void }) {
  const { song, currentId, replaceSong, setError } = useStore()
  const [minDur, setMinDur] = useState(song?.meta.min_dur_ms ?? 0)
  const [gap, setGap] = useState(song?.meta.merge_gap_ms ?? 0)
  const [fix, setFix] = useState(song?.meta.fix_octave ?? true)
  const [busy, setBusy] = useState(false)
  const edited = song?.notes.filter((n) => n.edited).length ?? 0

  async function apply() {
    if (!currentId) return
    if (edited > 0 && !window.confirm(`โน้ตที่คุณแก้ไว้ ${edited} ตัวจะถูกแทนที่ด้วยผลแกะใหม่ (ย้อนได้จาก "เวอร์ชันก่อนหน้า" ถ้าผ่านไปเกิน 2 นาทีแล้วเท่านั้น) ทำต่อไหม?`)) return
    setBusy(true)
    try {
      await useStore.getState().saveNow()
      replaceSong(await api.retranscribe(currentId, { fix_octave: fix, min_dur_ms: minDur, merge_gap_ms: gap }))
    } catch (e) { setError(`แกะใหม่ไม่สำเร็จ: ${e instanceof Error ? e.message : e}`) } finally { setBusy(false) }
  }

  return (
    <div className="sidepanel" data-testid="sens-panel">
      <b>ความละเอียดของโน้ต</b> <span className="muted">(แกะใหม่จากผลดิบ ไม่รันโมเดลซ้ำ เร็ว)</span>
      <label>ตัดโน้ตสั้นกว่า <b>{minDur}</b> ms <input type="range" min={0} max={400} step={10} value={minDur} onChange={(e) => setMinDur(+e.target.value)} /></label>
      <label>รวมโน้ตเดิมที่ห่างไม่เกิน <b>{gap}</b> ms <input type="range" min={0} max={300} step={10} value={gap} onChange={(e) => setGap(+e.target.value)} /></label>
      <label><input type="checkbox" checked={fix} onChange={(e) => setFix(e.target.checked)} /> แก้ octave อัตโนมัติตาม f0</label>
      <div><button onClick={() => void apply()} disabled={busy}>{busy ? 'กำลังแกะใหม่…' : 'แกะใหม่'}</button> <button onClick={onClose}>ปิด</button></div>
    </div>
  )
}

function HistoryPanel({ onClose }: { onClose: () => void }) {
  const { currentId, replaceSong, setError } = useStore()
  const [items, setItems] = useState<string[] | null>(null)
  useEffect(() => { if (currentId) void api.history(currentId).then(setItems).catch((e) => setError(String(e))) }, [currentId, setError])
  const label = (n: string) => n.replace(/^song-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})\.json$/, '$1-$2-$3 $4:$5:$6')

  async function restore(name: string) {
    if (!currentId || !window.confirm('กลับไปเวอร์ชันนี้? งานปัจจุบันจะถูกเก็บเป็นเวอร์ชันก่อนหน้าให้ (ถ้าไม่ถี่เกิน 2 นาที)')) return
    try { replaceSong(await api.restore(currentId, name)) } catch (e) { setError(`กู้เวอร์ชันไม่สำเร็จ: ${e instanceof Error ? e.message : e}`) }
  }

  return (
    <div className="sidepanel" data-testid="history-panel">
      <b>เวอร์ชันก่อนหน้า</b> <span className="muted">(เก็บอัตโนมัติ ≥ ทุก 2 นาที ล่าสุด 20 ชุด)</span>
      {items === null ? <div className="muted">กำลังโหลด…</div> : items.length === 0 ? <div className="muted">ยังไม่มี</div> : (
        <ul>{items.map((n) => <li key={n}>{label(n)} <button onClick={() => void restore(n)}>กู้คืน</button></li>)}</ul>
      )}
      <button onClick={onClose}>ปิด</button>
    </div>
  )
}
