import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { getTransport } from '../../audio/instance'
import type { TrackName } from '../../audio/transport'
import { useStore } from '../../store/store'
import { PianoRoll } from '../pianoroll/PianoRoll'

const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`
const TRACK_LABEL: Record<TrackName, string> = {
  mix: 'เพลงเต็ม', vocals: 'เสียงร้อง', instrumental: 'ดนตรี (ไม่มีร้อง)', lead: 'เสียงร้องนำ', backing: 'เสียงประสาน', lead_dry: 'ร้องนำ (ไม่มี reverb)',
}

export function Workspace() {
  const { song, currentId, view, setView, selectedNoteId, closeProject, setError } = useStore()
  const tr = getTransport()
  const [playing, setPlaying] = useState(false)
  const [track, setTrack] = useState<TrackName>('mix')
  const [synth, setSynth] = useState(false)
  const [click, setClick] = useState(false)
  const [split, setSplit] = useState(false)
  const [ready, setReady] = useState(false)
  const timeEl = useRef<HTMLSpanElement>(null)

  const tracks: TrackName[] = ['mix', 'vocals', 'instrumental',
    ...(song?.meta.karaoke ? (['lead', 'backing'] as TrackName[]) : []),
    ...(song?.meta.dereverb ? (['lead_dry'] as TrackName[]) : [])]

  useEffect(() => {
    if (!song || !currentId) return
    tr.clearTracks()
    setReady(false)
    setPlaying(false)
    tr.setSong(song.notes, song.beats)
    tr.onEnded = () => setPlaying(false)
    tr.loadTrack('mix', api.audioUrl(currentId, 'mix')).then(() => { setTrack('mix'); setReady(true) })
      .catch((e) => setError(`โหลดเสียงไม่สำเร็จ: ${e instanceof Error ? e.message : e}`))
    return () => { tr.pause() }
  }, [song, currentId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { tr.synthOn = synth }, [synth, tr])
  useEffect(() => { tr.clickOn = click }, [click, tr])
  useEffect(() => { tr.setSplit(split) }, [split, tr])

  // อัปเดตเวลาที่แสดง (ไม่ผ่าน React state เพื่อไม่ re-render ทุกเฟรม)
  useEffect(() => {
    let raf = 0
    const loop = () => {
      if (timeEl.current) timeEl.current.textContent = `${fmt(tr.getTime())} / ${fmt(tr.duration || song?.source.duration || 0)}`
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [tr, song])

  // ปุ่มลัด: Space เล่น/หยุด
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (e.code === 'Space' && !['INPUT', 'SELECT', 'BUTTON'].includes(el.tagName)) { e.preventDefault(); toggle() }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  })

  function toggle() {
    if (!ready) return
    if (tr.playing) { tr.pause(); setPlaying(false) } else { void tr.play(); setPlaying(true) }
  }

  async function changeTrack(t: TrackName) {
    if (!currentId) return
    try { await tr.loadTrack(t, api.audioUrl(currentId, t)); setTrack(t) } catch (e) { setError(String(e)) }
  }

  if (!song) return null
  const sel = song.notes.find((n) => n.id === selectedNoteId)
  const low = song.notes.filter((n) => n.confidence < 0.5 || n.octave_suspect).length

  return (
    <div className="workspace">
      <div className="infobar">
        <button onClick={closeProject} data-testid="back">← โปรเจกต์</button>
        <b className="title">{song.source.title}</b>
        <span>คีย์ <b data-testid="key">{song.key ? `${song.key.tonic} ${song.key.mode}` : '—'}</b></span>
        <span>BPM <b data-testid="bpm">{song.tempo.bpm ?? '—'}</b>{song.tempo.unstable && <span className="warn" title="Beat This! สลับ tempo ครึ่ง/เท่าตัวในบางช่วง"> ⚠ tempo ไม่นิ่ง</span>}</span>
        <span>{song.time_signature ? `${song.time_signature.num}/${song.time_signature.den}` : ''}</span>
        <span><b data-testid="notecount">{song.notes.length}</b> โน้ต</span>
        <span className={low ? 'warn' : 'muted'} title="โน้ตที่ความมั่นใจต่ำ หรือสงสัยว่าผิด octave (ขอบสีส้ม)">{low} ควรตรวจ</span>
      </div>

      <PianoRoll />

      <div className="transport">
        <button className="play" onClick={toggle} disabled={!ready} data-testid="play">{playing ? '⏸ หยุด' : '▶ เล่น'}</button>
        <span ref={timeEl} className="time" data-testid="time">0:00.0</span>
        <label>เสียง <select value={track} onChange={(e) => void changeTrack(e.target.value as TrackName)}>
          {tracks.map((t) => <option key={t} value={t}>{TRACK_LABEL[t]}</option>)}</select></label>
        <label><input type="checkbox" checked={synth} onChange={(e) => setSynth(e.target.checked)} /> เสียงโน้ต (synth)</label>
        <label title="เพลงออกหูซ้าย / synth ออกหูขวา เพื่อฟังเทียบว่าโน้ตตรงไหม"><input type="checkbox" checked={split} onChange={(e) => setSplit(e.target.checked)} /> ฟังเทียบ ซ้าย/ขวา</label>
        <label><input type="checkbox" checked={click} onChange={(e) => setClick(e.target.checked)} /> Metronome</label>
        <span className="spacer" />
        <label><input type="checkbox" checked={view.follow} onChange={(e) => setView({ follow: e.target.checked })} /> ตามเพลง</label>
        <label><input type="checkbox" checked={view.showF0} onChange={(e) => setView({ showF0: e.target.checked })} /> เส้น pitch จริง</label>
        <label><input type="checkbox" checked={view.highlightKey} onChange={(e) => setView({ highlightKey: e.target.checked })} /> ไฮไลต์คีย์</label>
        <label>ซูม <input type="range" min={15} max={400} value={view.pxPerSec} onChange={(e) => setView({ pxPerSec: +e.target.value })} /></label>
      </div>

      {sel && (
        <div className="notepanel" data-testid="notepanel">
          <b>{sel.name}</b> · MIDI {sel.midi} · {sel.freq} Hz · {sel.start.toFixed(2)}–{sel.end.toFixed(2)} s
          {sel.dur_beats !== undefined && <> · {sel.dur_beats} beat</>}
          · cents {sel.cents_offset ?? '—'} · ความมั่นใจ {(sel.confidence * 100).toFixed(0)}%
          {sel.octave_suspect && <span className="warn"> · ⚠ สงสัยผิด octave</span>}
        </div>
      )}
    </div>
  )
}
