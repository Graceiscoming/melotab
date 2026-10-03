import { useRef, useState } from 'react'
import { api } from '../../api/client'
import { useStore } from '../../store/store'
import { BatchPanel, ModelManager } from './LibraryTools'

const ACCEPT = '.mp3,.wav,.flac,.m4a,.ogg,.mp4,.webm,.opus,.mkv'

export function Library() {
  const { projects, jobs, refreshProjects, openProject, setError } = useStore()
  const [karaoke, setKaraoke] = useState(false)
  const [dereverb, setDereverb] = useState(false)
  const [busy, setBusy] = useState(false)
  const [drag, setDrag] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const running = (pid: string) => Object.values(jobs).some((j) => j.project_id === pid && (j.status === 'running' || j.status === 'queued'))

  async function importFile(file: File) {
    setBusy(true)
    try {
      const p = await api.upload(file)
      await refreshProjects()
      await api.analyze(p.id, { karaoke, dereverb })
      await openProject(p.id)
    } catch (e) {
      setError(`นำเข้าไม่สำเร็จ: ${e instanceof Error ? e.message : e}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="library">
      <div
        className={`dropzone ${drag ? 'drag' : ''}`}
        data-testid="dropzone"
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) void importFile(f) }}
        onClick={() => input.current?.click()}
      >
        <div className="big">🎸 ลากไฟล์เสียงมาวางที่นี่ หรือคลิกเพื่อเลือกไฟล์</div>
        <div className="muted">mp3 · wav · flac · m4a · ogg · mp4 — การวิเคราะห์เริ่มทันที{busy ? ' (กำลังอัปโหลด…)' : ''}</div>
        <input ref={input} type="file" accept={ACCEPT} hidden data-testid="fileinput"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void importFile(f); e.target.value = '' }} />
      </div>
      <div className="options">
        <label><input type="checkbox" checked={karaoke} onChange={(e) => setKaraoke(e.target.checked)} /> ตัดเสียงประสาน (karaoke) <span className="muted">— แม่นขึ้นถ้ามีเสียงประสาน แต่ช้า +~2 นาที/เพลง</span></label>
        <label><input type="checkbox" checked={dereverb} onChange={(e) => setDereverb(e.target.checked)} /> ลบ reverb <span className="muted">— +~1 นาที/เพลง</span></label>
      </div>

      <BatchPanel karaoke={karaoke} dereverb={dereverb} />
      <ModelManager />

      <h2>โปรเจกต์</h2>
      {projects.length === 0 ? <p className="muted">ยังไม่มีโปรเจกต์</p> : (
        <ul className="projects">
          {projects.map((p) => (
            <li key={p.id}>
              <button className="proj" onClick={() => void openProject(p.id)} disabled={!p.analyzed}>
                <b>{p.title}</b>
                <span className="muted">{p.analyzed ? 'วิเคราะห์แล้ว' : running(p.id) ? 'กำลังวิเคราะห์…' : 'ยังไม่ได้วิเคราะห์'}</span>
              </button>
              {!p.analyzed && !running(p.id) && <button onClick={() => void api.analyze(p.id, { karaoke, dereverb })}>วิเคราะห์</button>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
