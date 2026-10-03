import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import { useStore } from '../../store/store'
import { mergeAutoTechniques, toggleLock, toggleTechnique, lockAt, TUNINGS, TUNING_LABEL, type TechKey } from '../../tab/ops'
import { pcOf, scalePcs } from '../../theory/notes'
import type { Alternative, Block, KeyOption, KeySuggestion, TabEvent } from '../../types'
import { Fretboard } from './Fretboard'

const PRESET_LABEL: Record<string, string> = {
  balanced: 'สมดุล', vocal_like: 'ให้เหมือนเสียงร้อง (slide/legato)', easy: 'ง่ายที่สุด (ย้ายมือน้อย สายเปล่า)', bright: 'สว่าง (สายบาง)', warm: 'หนา (สายหนา)',
}
const WARN_LABEL: Record<string, string> = {
  hard_shift: 'เปลี่ยนตำแหน่งไม่ทัน', stretch: 'ต้องยืดนิ้ว', unplayable: 'เล่นไม่ได้', out_of_block: 'นอก block', octave_shifted: 'ย้าย octave',
}
const TECHS: { k: TechKey; label: string; key: string }[] = [
  { k: 'hammer', label: 'Hammer', key: 'H' }, { k: 'pull', label: 'Pull', key: 'P' }, { k: 'slide', label: 'Slide', key: 'S' },
  { k: 'bend', label: 'Bend', key: 'B' }, { k: 'release', label: 'Release', key: 'R' }, { k: 'vibrato', label: 'Vibrato', key: 'V' }, { k: 'grace', label: 'Grace', key: 'G' },
]

export function TabPanel() {
  const { song, currentId, tab, tabSettings: S, tabBusy, selectedNoteId, locked, techniques } = useStore()
  const setS = useStore((s) => s.setTabSettings)
  const [system, setSystem] = useState<'none' | 'position' | 'pentatonic'>('none')
  const [available, setAvailable] = useState<Block[]>([])
  const [coverage, setCoverage] = useState<number | null>(null)
  const [custom, setCustom] = useState({ min: 5, max: 9 })
  const [alts, setAlts] = useState<Alternative[] | null>(null)
  const [autoMsg, setAutoMsg] = useState('')
  const [suggest, setSuggest] = useState<KeySuggestion | 'loading' | null>(null)

  const notes = song?.notes
  const selEvent: TabEvent | undefined = tab?.events.find((e) => e.note_id === selectedNoteId)
  const selectedIds = useMemo(() => new Set(S.blocks.map((b) => b.id)), [S.blocks])

  // รายการ block ตามระบบ/คีย์/capo/จูนนิ่ง + coverage ของที่เลือก
  useEffect(() => {
    if (!currentId || !notes || system === 'none') { setAvailable([]); setCoverage(null); return }
    let dead = false
    api.blocks(currentId, { system, transpose: S.transpose, capo: S.capo, tuning: S.tuning, selected: S.blocks, notes })
      .then((r) => { if (!dead) { setAvailable(r.blocks); setCoverage(r.coverage) } })
      .catch(() => { if (!dead) setAvailable([]) })
    return () => { dead = true }
  }, [currentId, system, S.transpose, S.capo, S.tuning, S.blocks, notes])

  useEffect(() => { setAlts(null) }, [selectedNoteId, tab])

  if (!song) return null
  const tonicPc = song.key ? (pcOf(song.key.tonic) + S.transpose + 120) % 12 : null
  const pcs = S.blocks.length ? new Set(S.blocks.flatMap((b) => b.pcs)) : (song.key ? new Set([...scalePcs({ tonic: song.key.tonic, mode: song.key.mode })].map((p) => (p + S.transpose + 120) % 12)) : new Set<number>())

  const toggleBlock = (b: Block) => setS({ blocks: selectedIds.has(b.id) ? S.blocks.filter((x) => x.id !== b.id) : [...S.blocks, b] })
  const addCustom = () => {
    const lo = Math.max(0, Math.min(custom.min, custom.max))
    const hi = Math.min(S.max_fret, Math.max(custom.min, custom.max))
    const id = `custom-${lo}-${hi}`
    if (!selectedIds.has(id)) setS({ blocks: [...S.blocks, { id, label: `Custom (ช่อง ${lo}–${hi})`, system: 'custom', fret_min: lo, fret_max: hi, pcs: [] }] })
  }
  const edit = useStore.getState().editState

  async function loadAlts() {
    if (!currentId || !notes || !selEvent) return
    try { setAlts(await api.alternatives(currentId, selEvent.note_id, S, locked, notes)) } catch (e) { useStore.getState().setError(String(e)) }
  }
  async function autoTech() {
    if (!currentId || !notes) return
    setAutoMsg('กำลังตรวจ ornament…')
    try {
      const sug = await api.autoTechniques(currentId, S, locked, notes)
      let r = { added: 0, skipped: 0 }
      edit((st) => { const m = mergeAutoTechniques(st, sug); r = m; return m.added ? m.state : null })
      setAutoMsg(`ใส่เทคนิค ${r.added} โน้ต (ข้ามที่คุณใส่เองแล้ว ${r.skipped}, ตรวจพบ ornament ${sug.ornaments}, ทำไม่ได้จริง ${sug.rejected.length})`)
    } catch (e) { setAutoMsg(''); useStore.getState().setError(String(e)) }
  }
  async function loadSuggest() {
    if (!currentId || !notes) return
    setSuggest('loading')
    try { setSuggest(await api.suggestKeys(currentId, { ...S, blocks: [] }, notes)) } catch (e) { setSuggest(null); useStore.getState().setError(String(e)) }
  }
  const useOption = (o: KeyOption) => { setS({ transpose: o.transpose, capo: o.capo }); setSuggest(null) }

  return (
    <aside className="tabpanel" data-testid="tabpanel">
      <section>
        <h4>ตั้งค่าแทป</h4>
        <div className="grid2">
          <label>ยกคีย์ (semitone)<input type="number" min={-12} max={12} value={S.transpose} data-testid="transpose"
            onChange={(e) => setS({ transpose: Math.max(-12, Math.min(12, Number(e.target.value) || 0)) })} /></label>
          <label>Capo<input type="number" min={0} max={12} value={S.capo} data-testid="capo"
            onChange={(e) => setS({ capo: Math.max(0, Math.min(12, Number(e.target.value) || 0)) })} /></label>
        </div>
        <label>จูนนิ่ง<select value={S.tuning} onChange={(e) => setS({ tuning: e.target.value })} data-testid="tuning-select">
          {Object.keys(TUNINGS).map((t) => <option key={t} value={t}>{TUNING_LABEL[t]}</option>)}</select></label>
        <label>สไตล์การเลือกตำแหน่ง<select value={S.preset} onChange={(e) => setS({ preset: e.target.value })}>
          {Object.keys(PRESET_LABEL).map((p) => <option key={p} value={p}>{PRESET_LABEL[p]}</option>)}</select></label>
        <div className="row">
          <button className="primary" onClick={() => void useStore.getState().regenerateTab()} disabled={tabBusy} data-testid="gen-tab">{tabBusy ? 'กำลังสร้าง…' : tab ? 'สร้างแทปใหม่' : 'สร้างแทป'}</button>
          <button onClick={() => void loadSuggest()} data-testid="suggest-btn">แนะนำคีย์ / Capo</button>
          <button onClick={() => void autoTech()} disabled={!tab} title="แปลงลูกคอเสียงร้อง (vibrato/สไลด์/ไต่เสียง/ลากต่อ) เป็น ~ / b h p slide ตามกติกาที่เล่นได้จริง — ไม่ทับที่คุณใส่เอง" data-testid="auto-tech">เทคนิคอัตโนมัติ</button>
        </div>
        {autoMsg && <div className="muted small" data-testid="auto-tech-msg">{autoMsg}</div>}
        <div className="muted small">โน้ตที่ล็อก (🔒) จะไม่ถูกเปลี่ยนเมื่อสร้างใหม่ — ตำแหน่งที่คุณแก้เองจะถูกล็อกให้อัตโนมัติ</div>
      </section>

      {tab && (
        <section data-testid="tab-summary">
          <h4>ความยาก</h4>
          <div className="row">
            <b className="big" data-testid="difficulty">{tab.summary.difficulty}</b><span className="muted">/ 10 (ดัชนีโดยประมาณ)</span>
          </div>
          <div className="small">
            จุดยาก <b className={tab.summary.hard ? 'err' : ''} data-testid="hard-count">{tab.summary.hard}</b>
            {' · '}เล่นไม่ได้ <b className={tab.summary.unplayable ? 'err' : ''} data-testid="unplayable-count">{tab.summary.unplayable}</b>
            {S.blocks.length > 0 && <> {' · '}นอก block <b>{tab.summary.out_of_block}</b> · ย้าย octave <b>{tab.summary.octave_shifted}</b></>}
          </div>
        </section>
      )}

      <section>
        <h4>Block Mode (จำกัดโซนบนคอ)</h4>
        <label>ระบบ<select value={system} onChange={(e) => { setSystem(e.target.value as typeof system); if (e.target.value === 'none') setS({ blocks: [] }) }} data-testid="block-system">
          <option value="none">ไม่จำกัด</option><option value="position">ตำแหน่งตามสเกล (7)</option><option value="pentatonic">Pentatonic box (5)</option></select></label>
        {system !== 'none' && (
          <>
            <div className="chips" data-testid="block-list">
              {available.map((b) => (
                <button key={b.id} className={selectedIds.has(b.id) ? 'chip on' : 'chip'} onClick={() => toggleBlock(b)} title={b.label} data-testid="block-chip">{b.fret_min}–{b.fret_max}</button>
              ))}
            </div>
            <div className="row small">
              <label><input type="radio" checked={S.block_mode === 'multi'} onChange={() => setS({ block_mode: 'multi' })} /> ย้ายระหว่าง block ที่เลือกได้</label>
              <label><input type="radio" checked={S.block_mode === 'single'} onChange={() => setS({ block_mode: 'single' })} /> เล่นแค่ block แรก</label>
            </div>
            <label>โน้ตที่ไม่มีตำแหน่งใน block<select value={S.out_of_block} onChange={(e) => setS({ out_of_block: e.target.value as typeof S.out_of_block })} data-testid="oob">
              <option value="octave_shift">ย้าย octave อัตโนมัติ</option><option value="stretch">ยืดออกนอก block 1–3 ช่อง</option><option value="warn">เล่นนอก block + เตือน</option></select></label>
            {coverage !== null && <div className="small" data-testid="coverage">โน้ตของเพลงที่อยู่ใน block ที่เลือก: <b>{Math.round(coverage * 100)}%</b></div>}
          </>
        )}
        <div className="row small">Custom ช่อง
          <input type="number" min={0} max={22} value={custom.min} onChange={(e) => setCustom({ ...custom, min: Number(e.target.value) })} className="num" />–
          <input type="number" min={0} max={22} value={custom.max} onChange={(e) => setCustom({ ...custom, max: Number(e.target.value) })} className="num" />
          <button onClick={addCustom}>เพิ่ม</button>
          {S.blocks.some((b) => b.system === 'custom') && <button onClick={() => setS({ blocks: S.blocks.filter((b) => b.system !== 'custom') })}>ล้าง</button>}
        </div>
        {S.blocks.length > 0 && <div className="small muted">ที่เลือก: {S.blocks.map((b) => `${b.fret_min}–${b.fret_max}`).join(', ')} <button className="linkbtn" onClick={() => setS({ blocks: [] })}>ล้างทั้งหมด</button></div>}
        <Fretboard blocks={S.blocks} tuning={TUNINGS[S.tuning]} capo={S.capo} pcs={pcs} tonicPc={tonicPc} selected={selEvent} />
        <div className="muted small">จุดทอง = โน้ตหลักของคีย์ · วงแดง = โน้ตที่เลือก · เลขช่องนับจาก capo</div>
      </section>

      <section data-testid="sel-section">
        <h4>โน้ตที่เลือก</h4>
        {!selEvent ? <div className="muted small">คลิกเลขในแทป (Shift+คลิก = เลือกหลายตัว)</div> : (
          <>
            <div data-testid="sel-info">
              สาย <b>{selEvent.string ?? '—'}</b> ช่อง <b>{selEvent.fret ?? '—'}</b> · pitch {selEvent.pitch}
              {selEvent.finger ? ` · นิ้ว ${selEvent.finger}` : ''} · ยาก {(selEvent.difficulty * 100).toFixed(0)}%
              {selEvent.warnings.length > 0 && <div className="warn small">{selEvent.warnings.map((w) => WARN_LABEL[w] ?? w).join(' · ')}</div>}
            </div>
            <div className="row">
              <button onClick={() => edit((s) => toggleLock(s, selEvent))} data-testid="lock-btn">{locked[selEvent.note_id] ? '🔒 ปลดล็อก' : '🔓 ล็อก (L)'}</button>
              <button onClick={() => void loadAlts()} data-testid="alts-btn">ตำแหน่งทางเลือก</button>
            </div>
            {alts && (alts.length === 0 ? <div className="muted small">ไม่มีทางเลือกอื่น</div> : (
              <ul className="alts" data-testid="alts-list">
                {alts.map((a) => (
                  <li key={`${a.string}-${a.fret}`}>
                    <button onClick={() => { edit((s) => lockAt(s, selEvent.note_id, { string: a.string, fret: a.fret })); setAlts(null) }}>
                      สาย {a.string} ช่อง {a.fret}</button>
                    <span className="muted small"> {a.delta_cost > 0 ? `+${a.delta_cost}` : a.delta_cost} ต้นทุน{a.hard > 0 ? ` · จุดยาก +${a.hard}` : a.hard < 0 ? ` · จุดยาก ${a.hard}` : ''}</span>
                  </li>
                ))}
              </ul>
            ))}
            <div className="chips">
              {TECHS.map((t) => {
                const tt = techniques[selEvent.note_id]
                const on = t.k === 'hammer' || t.k === 'pull' || t.k === 'slide' ? tt?.to_next === t.k : t.k === 'grace' ? tt?.in === 'grace' : !!tt?.on?.includes(t.k)
                return <button key={t.k} className={on ? 'chip on' : 'chip'} onClick={() => edit((s) => toggleTechnique(s, selEvent.note_id, t.k))} title={`${t.label} (${t.key})`}>{t.key}</button>
              })}
            </div>
            <div className="muted small">H hammer · P pull · S slide · B bend · R release · V vibrato · G grace (กดซ้ำ = ถอด)</div>
          </>
        )}
      </section>

      {suggest && (
        <div className="modal" data-testid="suggest-modal" onClick={() => setSuggest(null)}>
          <div className="modalbox" onClick={(e) => e.stopPropagation()}>
            <div className="row"><b>แนะนำคีย์ที่เล่นง่าย + Capo</b><span className="spacer" /><button onClick={() => setSuggest(null)}>ปิด</button></div>
            {suggest === 'loading' ? <p className="muted">กำลังลองทุกคีย์ (13 × 8 แบบ)…</p> : (
              <>
                <p className="muted small">คีย์ต้นฉบับ {suggest.original_key} · คะแนนเป็น heuristic เทียบกันในเพลงนี้เท่านั้น (ยังไม่รวมความง่ายของคอร์ด) · เรียงให้แบบที่เล่นได้ครบทุกโน้ตก่อน</p>
                <OptionTable title="เสียงเท่าต้นฉบับ (ใช้ capo)" rows={suggest.same_sound} cur={S} onUse={useOption} />
                <OptionTable title="เปลี่ยนคีย์ (เสียงต่างจากต้นฉบับ)" rows={suggest.transposed} cur={S} onUse={useOption} />
              </>
            )}
          </div>
        </div>
      )}
    </aside>
  )
}

function OptionTable({ title, rows, cur, onUse }: { title: string; rows: KeyOption[]; cur: { transpose: number; capo: number }; onUse: (o: KeyOption) => void }) {
  return (
    <>
      <h5>{title}</h5>
      <table className="opts" data-testid="suggest-table">
        <thead><tr><th>#</th><th>เสียงจริง</th><th>รูปมือ</th><th>Capo</th><th>ยก</th><th>ยาก</th><th>จุดยาก</th><th>โน้ตหาย</th><th /></tr></thead>
        <tbody>
          {rows.map((o, i) => (
            <tr key={`${o.transpose}-${o.capo}`} className={o.transpose === cur.transpose && o.capo === cur.capo ? 'cur' : ''}>
              <td>{i === 0 ? '⭐' : i + 1}</td><td>{o.sounding_key}</td><td>{o.shape_key}{o.friendly ? ' ✓' : ''}</td><td>{o.capo}</td>
              <td>{o.transpose > 0 ? '+' : ''}{o.transpose}</td><td>{o.difficulty}/10</td><td>{o.hard}</td><td className={o.unplayable ? 'err' : ''}>{o.unplayable}</td>
              <td><button onClick={() => onUse(o)} data-testid="use-option">ใช้</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
