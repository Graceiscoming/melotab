import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useStore } from '../../store/store'

const gb = (b: number) => (b / 1e9).toFixed(2)

/** Batch Mode: วาง path ไฟล์ (บรรทัดละไฟล์) หรือโฟลเดอร์ แล้วใส่คิววิเคราะห์ทั้งหมด (ทำทีละงาน ปล่อยทิ้งข้ามคืนได้) */
export function BatchPanel({ karaoke, dereverb }: { karaoke: boolean; dereverb: boolean }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  async function run() {
    const lines = text.split('\n').map((l) => l.trim().replace(/^"|"$/g, '')).filter(Boolean)
    if (!lines.length) return
    setBusy(true); setMsg('')
    try {
      // บรรทัดที่ไม่มีนามสกุลไฟล์เสียง = โฟลเดอร์
      const isFile = (l: string) => /\.(mp3|wav|flac|m4a|aac|ogg|opus|mp4|mkv|webm|mov)$/i.test(l)
      const paths = lines.filter(isFile)
      const folders = lines.filter((l) => !isFile(l))
      let created = 0
      const errs: string[] = []
      for (const [i, folder] of (folders.length ? folders : [null]).entries()) {
        const r = await api.batch({ paths: i === 0 ? paths : [], folder, options: { karaoke, dereverb } })
        created += r.created.length
        errs.push(...r.errors.map((e) => `${e.path}: ${e.error}`))
      }
      setMsg(`ใส่คิวแล้ว ${created} เพลง${errs.length ? ` · ผิดพลาด ${errs.length}: ${errs.join(' | ')}` : ''}`)
      await useStore.getState().refreshProjects()
    } catch (e) { setMsg(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  return (
    <details className="tools" data-testid="batch">
      <summary>Batch Mode — วิเคราะห์หลายเพลงต่อเนื่อง</summary>
      <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} data-testid="batch-text"
        placeholder={'วาง path ไฟล์เสียง (บรรทัดละไฟล์) หรือโฟลเดอร์\nD:\\music\\song1.mp3\nD:\\music\\album'} />
      <div className="row"><button onClick={() => void run()} disabled={busy || !text.trim()} data-testid="batch-run">{busy ? 'กำลังใส่คิว…' : 'ใส่คิววิเคราะห์'}</button>
        <span className="muted small">ใช้ตัวเลือก karaoke/de-reverb ด้านบน · ลิงก์ YouTube ยังไม่รองรับ (ติด 403)</span></div>
      {msg && <p className="small" data-testid="batch-msg">{msg}</p>}
    </details>
  )
}

/** Model Manager: ดูโมเดล/ขนาด/VRAM ที่วัดจริง และลบตัวที่ดาวน์โหลดอัตโนมัติ (จะโหลดใหม่เมื่อใช้ครั้งหน้า) */
export function ModelManager() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.models>> | null>(null)
  const [err, setErr] = useState('')
  const load = () => api.models().then(setData).catch((e) => setErr(String(e)))
  useEffect(() => { void load() }, [])
  async function del(id: string, name: string) {
    if (!window.confirm(`ลบ ${name}? (ดาวน์โหลดใหม่อัตโนมัติเมื่อใช้งานครั้งหน้า)`)) return
    try { await api.deleteModel(id); await load() } catch (e) { setErr(e instanceof Error ? e.message : String(e)) }
  }
  return (
    <details className="tools" data-testid="models">
      <summary>Model Manager{data ? ` — ${gb(data.total_bytes)} GB · ดิสก์ว่าง ${gb(data.disk_free_bytes)} GB` : ''}</summary>
      {err && <p className="err small">{err}</p>}
      {data && (
        <table className="opts">
          <thead><tr><th>โมเดล</th><th>หน้าที่</th><th>สถานะ</th><th>ขนาด</th><th>VRAM*</th><th /></tr></thead>
          <tbody>
            {data.models.map((m) => (
              <tr key={m.id} data-testid="model-row">
                <td>{m.name}{m.required ? '' : <span className="muted"> (ไม่บังคับ)</span>}</td><td>{m.role}</td>
                <td className={m.present ? '' : 'err'}>{m.present ? '✓ พร้อม' : 'ไม่พบ'}</td><td>{gb(m.size_bytes)} GB</td><td>~{m.vram_gb} GB</td>
                <td>{m.deletable && <button onClick={() => void del(m.id, m.name)}>ลบ</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="muted small">*VRAM ที่วัดจริงบน RTX 4060 (DECISIONS.md) · SOME/RMVPE/BTC ติดตั้งเอง ลบจาก UI ไม่ได้ · โฟลเดอร์ {data?.models_dir}</p>
    </details>
  )
}
