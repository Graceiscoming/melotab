import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useStore } from '../../store/store'

const STAGE_LABEL: Record<string, string> = {
  ingest: 'เตรียมไฟล์เสียง', separation: 'แยกเสียงร้อง', karaoke: 'ตัดเสียงประสาน', dereverb: 'ลบ reverb',
  f0: 'Pitch เสียงร้อง', notes: 'แกะโน้ต', rhythm: 'จังหวะ',
}
const STATUS_ICON: Record<string, string> = { start: '🔄', done: '✅', cached: '⚡', pending: '⏳' }

export function StatusBar() {
  const { connected, lastHeartbeat, stats, jobs, stageRows } = useStore()
  const [open, setOpen] = useState(false)
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t) }, [])

  const list = Object.values(jobs).sort((a, b) => b.id.localeCompare(a.id))
  const active = list.find((j) => j.status === 'running' || j.status === 'queued')
  const shown = active ?? list[0]
  const stalled = connected && lastHeartbeat > 0 && now - lastHeartbeat > 10000
  const g = stats?.gpu

  return (
    <footer className="statusbar" data-testid="statusbar">
      {open && shown && (
        <div className="jobpanel" data-testid="jobpanel">
          <b>งานล่าสุด</b> <span className="muted">{shown.id} · {shown.status}</span>
          {(stageRows[shown.id] ?? []).map((r) => (
            <div key={r.stage}>
              {STATUS_ICON[r.status]} {STAGE_LABEL[r.stage] ?? r.stage}
              {r.seconds !== undefined && <span className="muted"> {r.seconds}s{r.status === 'cached' ? ' (cache)' : ''}</span>}
            </div>
          ))}
          {shown.error && <div className="err">{shown.error}</div>}
        </div>
      )}
      <div className="row">
        <span className={connected ? 'dot ok' : 'dot bad'} />
        {!connected ? (
          <span className="err">ไม่ได้เชื่อมต่อ backend — เปิดด้วย <code>uvicorn melotab.api.app:app --port 8000</code></span>
        ) : stalled ? (
          <span className="err">backend ไม่ตอบสนอง ({Math.round((now - lastHeartbeat) / 1000)} วินาที)</span>
        ) : active ? (
          <>
            <button className="link" onClick={() => setOpen(!open)}>
              กำลังวิเคราะห์: {STAGE_LABEL[active.stage ?? ''] ?? (active.status === 'queued' ? 'รอคิว' : '…')}
            </button>
            <div className="bar"><div style={{ width: `${active.overall_pct}%` }} /></div>
            <span>{Math.round(active.overall_pct)}%</span>
            <button onClick={() => void api.cancel(active.id)}>ยกเลิก</button>
          </>
        ) : shown ? (
          <button className="link" onClick={() => setOpen(!open)}>
            งานล่าสุด: {shown.status === 'done' ? '✓ เสร็จ' : shown.status === 'error' ? '✗ ล้มเหลว' : shown.status}
          </button>
        ) : <span className="muted">พร้อมใช้งาน</span>}
        <span className="spacer" />
        {stats && (
          <span className="stats">
            {g ? <>GPU {g.util_pct}% · VRAM {g.vram_used_gb}/{g.vram_total_gb} GB · {g.temp_c}°C{g.temp_c >= 85 ? ' ⚠' : ''} │ </> : 'ไม่พบ GPU │ '}
            CPU {Math.round(stats.cpu_pct)}% │ RAM {stats.ram_used_gb}/{stats.ram_total_gb} GB
          </span>
        )}
      </div>
    </footer>
  )
}
