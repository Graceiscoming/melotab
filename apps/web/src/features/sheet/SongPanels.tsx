import { useState } from 'react'
import { api } from '../../api/client'
import { useStore } from '../../store/store'
import type { Section } from '../../types'

/** แผงจัดการเนื้อร้อง (ถอดด้วย ASR / วางเนื้อเอง) และท่อนเพลง (เปลี่ยนชื่อ/ขอบ/ลบ/เพิ่ม) */
export function SongPanels() {
  const [open, setOpen] = useState<'' | 'lyrics' | 'sections'>('')
  const song = useStore((s) => s.song)
  if (!song) return null
  return (
    <div className="songpanels" data-testid="songpanels">
      <div className="row">
        <button className={open === 'lyrics' ? 'on' : ''} onClick={() => setOpen(open === 'lyrics' ? '' : 'lyrics')} data-testid="open-lyrics">
          เนื้อร้อง {song.lyrics ? `(${song.lyrics.source === 'pasted' ? 'วางเอง' : 'ASR'} · ${song.lyrics.lines.length} บรรทัด)` : '(ยังไม่มี)'}</button>
        <button className={open === 'sections' ? 'on' : ''} onClick={() => setOpen(open === 'sections' ? '' : 'sections')} data-testid="open-sections">
          ท่อน ({song.sections?.length ?? 0})</button>
      </div>
      {open === 'lyrics' && <LyricsPanel />}
      {open === 'sections' && <SectionsPanel />}
    </div>
  )
}

function LyricsPanel() {
  const { song, currentId, setError, openProject } = useStore()
  const [text, setText] = useState(song?.lyrics?.text ?? song?.lyrics?.lines.map((l) => l.text).join('\n') ?? '')
  const [model, setModel] = useState('large-v3')
  const [lang, setLang] = useState('')
  const [busy, setBusy] = useState(false)
  if (!song || !currentId) return null

  async function runAsr(withText: boolean) {
    setBusy(true)
    try {
      await api.lyrics(currentId!, { model_size: model, language: lang || null, text: withText ? text : null, force_asr: false })
    } catch (e) { setError(`ถอดเนื้อร้องไม่สำเร็จ: ${e instanceof Error ? e.message : e}`) } finally { setBusy(false) }
  }
  async function align() {
    if (!text.trim()) return
    setBusy(true)
    try {
      await useStore.getState().saveNow()
      await api.lyricsAlign(currentId!, text)
      await openProject(currentId!)
    } catch (e) { setError(`จัดเวลาเนื้อไม่สำเร็จ: ${e instanceof Error ? e.message : e}`) } finally { setBusy(false) }
  }
  return (
    <div className="panelbox" data-testid="lyrics-panel">
      <p className="muted small">ASR ถอดเสียงร้องเพลงได้ไม่แม่นนัก (โดยเฉพาะภาษาไทย) — วางเนื้อที่ถูกต้องทีละบรรทัดด้านล่างแล้วกด "จัดเวลา" ระบบจะเทียบกับผล ASR เพื่อหาเวลา (โดยประมาณ ไม่ใช่ forced alignment ระดับโมเดลเสียง) งานถอดเสียงใช้เวลาประมาณ 1–2 นาทีต่อเพลง และครั้งแรกจะดาวน์โหลดโมเดล</p>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} placeholder="วางเนื้อเพลงที่นี่ ทีละบรรทัด" data-testid="lyrics-text" />
      <div className="row">
        <label>โมเดล<select value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="large-v3">large-v3 (แม่นสุด ~3 GB VRAM)</option><option value="medium">medium</option><option value="small">small (เร็ว)</option></select></label>
        <label>ภาษา<select value={lang} onChange={(e) => setLang(e.target.value)}>
          <option value="">ตรวจเอง</option><option value="th">ไทย</option><option value="en">อังกฤษ</option></select></label>
      </div>
      <div className="row">
        <button className="primary" disabled={busy} onClick={() => void runAsr(!!text.trim() && song!.lyrics?.source === 'pasted')} data-testid="run-asr">ถอดเสียงด้วย ASR</button>
        <button disabled={busy || !text.trim()} onClick={() => void align()} data-testid="align-btn">จัดเวลาเนื้อที่วาง</button>
      </div>
      {song.lyrics && <div className="muted small">ภาษาที่ตรวจพบ: {song.lyrics.language ?? '—'} · โมเดล {song.lyrics.model ?? '—'}</div>}
    </div>
  )
}

function SectionsPanel() {
  const { song, patchSong } = useStore()
  if (!song) return null
  const secs = song.sections ?? []
  const barsTotal = (secs[secs.length - 1]?.end_bar ?? 1) - 1
  const update = (id: string, patch: Partial<Section>) =>
    patchSong((s) => ({ ...s, sections: (s.sections ?? []).map((x) => (x.id === id ? { ...x, ...patch, auto: false } : x)) }))

  return (
    <div className="panelbox" data-testid="sections-panel">
      <p className="muted small">ท่อนเพลงมาจากการประมาณอัตโนมัติ (ไม่ใช่ allin1) — แก้ชื่อ/ห้องเริ่มได้ ท่อนที่แก้เองจะมีเครื่องหมาย ✎</p>
      <table className="opts">
        <thead><tr><th>ชื่อ</th><th>ห้องเริ่ม</th><th>ห้องจบ</th><th /></tr></thead>
        <tbody>
          {secs.map((sec, i) => (
            <tr key={sec.id}>
              <td><input value={sec.label} onChange={(e) => update(sec.id, { label: e.target.value })} data-testid="sec-label" /></td>
              <td><input type="number" className="num" min={1} max={barsTotal} value={sec.start_bar} disabled={i === 0} data-testid="sec-start"
                onChange={(e) => {
                  const v = Math.max(1, Math.min(barsTotal, Number(e.target.value) || 1))
                  patchSong((s) => ({ ...s, sections: (s.sections ?? []).map((x, k) => k === i ? { ...x, start_bar: v, auto: false } : k === i - 1 ? { ...x, end_bar: v, auto: false } : x) }))
                }} /></td>
              <td>{sec.end_bar - 1}</td>
              <td><button onClick={() => patchSong((s) => ({ ...s, sections: mergeAway(s.sections ?? [], i) }))} title="รวมเข้ากับท่อนก่อนหน้า (หรือถัดไป)">ลบ</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">ห้องเริ่มของท่อนแรกคงที่ที่ห้อง 1 · เวลา (วินาที) ของท่อนจะคำนวณใหม่เมื่อวิเคราะห์ซ้ำ</p>
    </div>
  )
}

/** ลบท่อนที่ index i โดยให้ท่อนก่อนหน้า (หรือถัดไปถ้าเป็นท่อนแรก) ขยายครอบ — ท่อนต้องต่อกันพอดีเสมอ */
export function mergeAway(secs: Section[], i: number): Section[] {
  if (secs.length <= 1) return secs
  const out = secs.map((s) => ({ ...s }))
  if (i > 0) {
    out[i - 1].end_bar = out[i].end_bar
    out[i - 1].end = out[i].end
    out[i - 1].auto = false
  } else {
    out[1].start_bar = out[0].start_bar
    out[1].start = out[0].start
    out[1].auto = false
  }
  out.splice(i, 1)
  return out
}
