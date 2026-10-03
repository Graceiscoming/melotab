import { useState } from 'react'
import { api, API } from '../../api/client'
import { useStore } from '../../store/store'

const FORMATS: { k: string; label: string }[] = [
  { k: 'png', label: 'PNG (รูปแทปรายท่อน)' },
  { k: 'svg', label: 'SVG' },
  { k: 'pdf', label: 'PDF (รวมเป็นเล่ม)' },
  { k: 'midi', label: 'MIDI (.mid)' },
  { k: 'musicxml', label: 'MusicXML (MuseScore)' },
  { k: 'gp5', label: 'Guitar Pro 5 (.gp5)' },
  { k: 'txt', label: 'Text tab (.txt)' },
  { k: 'chordsheet', label: 'Chord sheet (.txt)' },
  { k: 'lrc', label: 'เนื้อร้อง LRC' },
  { k: 'stems', label: 'Stems (vocals/instrumental)' },
  { k: 'video', label: 'วิดีโอแทปวิ่ง MP4 (ต่อท่อน · ใช้เวลา)' },
  { k: 'harmony', label: 'ไลน์ประสาน (MIDI + tab)' },
]
const PRESETS = [
  ['youtube', '1920×1080 (YouTube/จอ)'], ['ig_portrait', '1080×1350 (IG portrait)'], ['story', '1080×1920 (Story/TikTok)'], ['a4', 'A4 (พิมพ์)'],
] as const

interface Result { dir: string; files: { name: string; size: number; format: string }[]; skipped: { format: string; reason: string }[] }

export function ExportDialog({ onClose }: { onClose: () => void }) {
  const { song, currentId, tab } = useStore()
  const [fmts, setFmts] = useState<Set<string>>(new Set(['png']))
  const [secs, setSecs] = useState<'all' | 'whole' | string[]>('all')
  const [preset, setPreset] = useState('youtube')
  const [theme, setTheme] = useState('light')
  const [scale, setScale] = useState(2)
  const [chords, setChords] = useState(true)
  const [lyrics, setLyrics] = useState(true)
  const [watermark, setWatermark] = useState('')
  const [hInterval, setHInterval] = useState('third')
  const [hDir, setHDir] = useState('above')
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<Result | null>(null)
  const [err, setErr] = useState('')
  if (!song || !currentId) return null
  const sections = song.sections ?? []
  const imgOn = ['png', 'svg', 'pdf', 'video'].some((f) => fmts.has(f))

  const toggle = (k: string) => setFmts((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n })
  const toggleSec = (id: string) => setSecs((s) => { const cur = Array.isArray(s) ? s : []; return cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id] })

  async function run() {
    setBusy(true); setErr(''); setRes(null)
    try {
      await useStore.getState().saveNow() // export อ่านจากไฟล์ที่บันทึกไว้ → บันทึกสถานะล่าสุด (โน้ต/แทป/เทคนิค) ก่อน
      const sel = secs === 'all' ? 'all' : secs === 'whole' ? [] : secs
      setRes(await api.exportProject(currentId!, { formats: [...fmts], sections: sel, preset, theme, scale, harmony: { interval: hInterval, direction: hDir }, show_chords: chords, show_lyrics: lyrics, watermark }))
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }

  return (
    <div className="modal" data-testid="export-modal" onClick={onClose}>
      <div className="modalbox" onClick={(e) => e.stopPropagation()}>
        <div className="row"><b>Export</b><span className="spacer" /><button onClick={onClose}>ปิด</button></div>
        {!tab && <p className="warn small">ยังไม่มีแทป — ฟอร์แมตที่ต้องใช้แทปจะถูกข้าม (เปิดโหมด Guitar Tab เพื่อสร้างก่อน)</p>}
        <h5>ฟอร์แมต</h5>
        <div className="chips">
          {FORMATS.map((f) => (
            <label key={f.k} className="chip-check"><input type="checkbox" checked={fmts.has(f.k)} onChange={() => toggle(f.k)} data-testid={`fmt-${f.k}`} /> {f.label}</label>
          ))}
        </div>
        {imgOn && (
          <>
            <h5>รูปแทป: ท่อนที่จะ export</h5>
            <div className="chips">
              <label className="chip-check"><input type="radio" checked={secs === 'all'} onChange={() => setSecs('all')} /> ทุกท่อน (แยกไฟล์ต่อท่อน)</label>
              <label className="chip-check"><input type="radio" checked={secs === 'whole'} onChange={() => setSecs('whole')} /> ทั้งเพลง</label>
              <label className="chip-check"><input type="radio" checked={Array.isArray(secs)} onChange={() => setSecs([])} /> เลือกท่อน</label>
            </div>
            {Array.isArray(secs) && (
              <div className="chips" data-testid="export-sections">
                {sections.map((s) => <label key={s.id} className="chip-check"><input type="checkbox" checked={secs.includes(s.id)} onChange={() => toggleSec(s.id)} /> {s.label}</label>)}
                {sections.length === 0 && <span className="muted small">เพลงนี้ยังไม่มีท่อน</span>}
              </div>
            )}
            <div className="row small">
              <label>ขนาด <select value={preset} onChange={(e) => setPreset(e.target.value)} data-testid="export-preset">{PRESETS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
              <label>ธีม <select value={theme} onChange={(e) => setTheme(e.target.value)}><option value="light">สว่าง</option><option value="dark">มืด</option><option value="transparent">โปร่งใส (PNG)</option></select></label>
              <label>ความละเอียด <select value={scale} onChange={(e) => setScale(+e.target.value)}><option value={1}>1×</option><option value={2}>2×</option><option value={3}>3×</option></select></label>
            </div>
            <div className="row small">
              <label><input type="checkbox" checked={chords} onChange={(e) => setChords(e.target.checked)} /> แถวคอร์ด</label>
              <label><input type="checkbox" checked={lyrics} onChange={(e) => setLyrics(e.target.checked)} /> เนื้อร้อง</label>
              <label>ลายน้ำ <input value={watermark} onChange={(e) => setWatermark(e.target.value)} placeholder="ชื่อเพจ (ไม่ใส่ก็ได้)" /></label>
            </div>
          </>
        )}
        {fmts.has('harmony') && (
          <div className="row small">
            <label>ไลน์ประสาน <select value={hInterval} onChange={(e) => setHInterval(e.target.value)}><option value="third">3rd</option><option value="sixth">6th</option></select></label>
            <label><select value={hDir} onChange={(e) => setHDir(e.target.value)}><option value="above">เหนือเมโลดี้</option><option value="below">ใต้เมโลดี้</option></select></label>
          </div>
        )}
        <div className="row"><button className="primary" onClick={() => void run()} disabled={busy || fmts.size === 0} data-testid="export-run">{busy ? 'กำลัง export…' : 'Export'}</button></div>
        {err && <p className="err small" data-testid="export-error">{err}</p>}
        {res && (
          <div data-testid="export-result">
            <p className="small">บันทึกไว้ที่ <code>{res.dir}</code></p>
            <ul className="alts">
              {res.files.map((f) => (
                <li key={f.name}><a href={`${API}/projects/${encodeURIComponent(currentId)}/exports/${encodeURIComponent(f.name)}`} download={f.name} data-testid="export-file">{f.name}</a>
                  <span className="muted small"> {(f.size / 1024).toFixed(0)} KB</span></li>
              ))}
            </ul>
            {res.skipped.map((s) => <p key={s.format} className="warn small">ข้าม {s.format}: {s.reason}</p>)}
          </div>
        )}
      </div>
    </div>
  )
}
