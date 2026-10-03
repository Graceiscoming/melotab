import { create } from 'zustand'
import { api, wsUrl } from '../api/client'
import { withBeatPositions } from '../theory/rhythm'
import { patchEventsOptimistic, TUNINGS, type State as EditState } from '../tab/ops'
import type {
  F0Curve, FretPos, JobInfo, ProjectMeta, Song, StageEvent, SystemStats, TabEvent, TabSettings, TabSummary, Techniques,
} from '../types'

export interface StageRow {
  stage: string
  status: StageEvent['status'] | 'pending'
  seconds?: number
}

interface View {
  showF0: boolean
  highlightKey: boolean
  follow: boolean
  pxPerSec: number
  labels: boolean
  snap: boolean
  mode: 'roll' | 'tab' | 'sheet'
  heatmap: boolean
}

export type SaveState = 'saved' | 'dirty' | 'saving' | 'error'
const HISTORY_LIMIT = 300
const AUTOSAVE_MS = 1200
const REGEN_MS = 450
let saveTimer: number | undefined
let regenTimer: number | undefined
let regenSeq = 0

export const DEFAULT_TAB_SETTINGS: TabSettings = {
  transpose: 0, capo: 0, tuning: 'standard', max_fret: 22, blocks: [], block_mode: 'multi', out_of_block: 'octave_shift', preset: 'balanced',
}

/** snapshot สำหรับ undo/redo: ทุกอย่างที่ผู้ใช้แก้ได้ (โน้ต + ตำแหน่งที่ล็อกในแทป + เทคนิค) */
type Snapshot = EditState

interface TabData { events: TabEvent[]; summary: TabSummary }

interface State {
  // เชื่อมต่อ backend
  connected: boolean
  lastHeartbeat: number
  stats: SystemStats | null
  // โปรเจกต์
  projects: ProjectMeta[]
  currentId: string | null
  song: Song | null
  f0: F0Curve | null
  error: string | null
  // งานวิเคราะห์
  jobs: Record<string, JobInfo>
  stageRows: Record<string, StageRow[]> // job_id → ขั้นต่าง ๆ ที่เห็นมาแล้ว
  // การดู
  view: View
  selectedNoteId: string | null
  tabSel: string[] // โน้ตที่เลือกในแทป (หลายตัวได้ด้วย Shift+คลิก) — ตัวแรกสุดท้ายคือ selectedNoteId
  // การแก้ไข
  past: Snapshot[]
  future: Snapshot[]
  saveState: SaveState
  focus: { t: number; n: number } | null // ขอให้ piano roll เลื่อนไปที่เวลานี้ (n เพิ่มทุกครั้งเพื่อให้ effect ทำงานซ้ำได้)
  // แทป
  tab: TabData | null
  tabSettings: TabSettings
  locked: Record<string, FretPos>
  techniques: Record<string, Techniques>
  tabBusy: boolean
  tabVersion: number // เพิ่มทุกครั้งที่ได้ผลแทปใหม่จาก engine (ให้เทสต์/UI รู้ว่าผลล่าสุดมาถึงแล้ว)

  editState: (fn: (s: Snapshot) => Snapshot | null, select?: string | null) => void
  patchSong: (fn: (song: Song) => Song) => void // แก้ข้อมูลระดับเพลง (คอร์ด/ท่อน/เนื้อร้อง) ไม่ผ่านระบบ undo แต่มี autosave + เวอร์ชันก่อนหน้า
  editNotes: (fn: (notes: Snapshot['notes']) => Snapshot['notes'], select?: string | null) => void
  undo: () => void
  redo: () => void
  replaceSong: (song: Song) => void // ใช้หลัง retranscribe / restore: ล้างประวัติ undo
  requestFocus: (t: number) => void
  saveNow: () => Promise<void>
  setTabSettings: (patch: Partial<TabSettings>) => void
  regenerateTab: () => Promise<void>
  toggleTabSel: (id: string) => void
  refreshProjects: () => Promise<void>
  openProject: (id: string) => Promise<void>
  closeProject: () => void
  setError: (e: string | null) => void
  setView: (v: Partial<View>) => void
  selectNote: (id: string | null) => void
  connect: () => () => void
}

function scheduleSave(get: () => State) {
  clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => void get().saveNow(), AUTOSAVE_MS)
}
function scheduleRegen(get: () => State) {
  if (!get().tab) return // ยังไม่เคยสร้างแทป ไม่ต้องสร้างให้เอง
  clearTimeout(regenTimer)
  regenTimer = window.setTimeout(() => void get().regenerateTab(), REGEN_MS)
}

export const useStore = create<State>((set, get) => ({
  connected: false,
  lastHeartbeat: 0,
  stats: null,
  projects: [],
  currentId: null,
  song: null,
  f0: null,
  error: null,
  jobs: {},
  stageRows: {},
  view: { showF0: true, highlightKey: true, follow: true, pxPerSec: 90, labels: true, snap: true, mode: 'roll', heatmap: false },
  selectedNoteId: null,
  tabSel: [],
  past: [],
  future: [],
  saveState: 'saved',
  focus: null,
  tab: null,
  tabSettings: DEFAULT_TAB_SETTINGS,
  locked: {},
  techniques: {},
  tabBusy: false,
  tabVersion: 0,

  editState: (fn, select) => {
    const { song, past, locked, techniques } = get()
    if (!song) return
    const cur: Snapshot = { notes: song.notes, locked, techniques }
    const next = fn(cur)
    if (!next || (next.notes === cur.notes && next.locked === cur.locked && next.techniques === cur.techniques)) return
    const notes = next.notes === cur.notes ? cur.notes : withBeatPositions(next.notes, song.beats)
    const tab = get().tab
    set({
      song: { ...song, notes },
      locked: next.locked,
      techniques: next.techniques,
      ...(tab ? { tab: { ...tab, events: patchEventsOptimistic(tab.events, notes, next.locked, get().tabSettings).map((e) => ({ ...e, techniques: next.techniques[e.note_id] ?? {} })) } } : {}),
      past: [...past, cur].slice(-HISTORY_LIMIT),
      future: [],
      saveState: 'dirty',
      ...(select !== undefined ? { selectedNoteId: select, tabSel: select ? [select] : [] } : {}),
    })
    scheduleSave(get)
    scheduleRegen(get)
  },
  patchSong: (fn) => {
    const song = get().song
    if (!song) return
    set({ song: fn(song), saveState: 'dirty' })
    scheduleSave(get)
  },
  editNotes: (fn, select) => get().editState((s) => ({ ...s, notes: fn(s.notes) }), select),
  undo: () => {
    const { song, past, future, locked, techniques } = get()
    if (!song || past.length === 0) return
    const prev = past[past.length - 1]
    const tab0 = get().tab
    set({
      song: { ...song, notes: prev.notes }, locked: prev.locked, techniques: prev.techniques,
      ...(tab0 ? { tab: { ...tab0, events: patchEventsOptimistic(tab0.events, prev.notes, prev.locked, get().tabSettings) } } : {}),
      past: past.slice(0, -1), future: [{ notes: song.notes, locked, techniques }, ...future], saveState: 'dirty',
    })
    scheduleSave(get)
    scheduleRegen(get)
  },
  redo: () => {
    const { song, past, future, locked, techniques } = get()
    if (!song || future.length === 0) return
    const nxt = future[0]
    const tab1 = get().tab
    set({
      song: { ...song, notes: nxt.notes }, locked: nxt.locked, techniques: nxt.techniques,
      ...(tab1 ? { tab: { ...tab1, events: patchEventsOptimistic(tab1.events, nxt.notes, nxt.locked, get().tabSettings) } } : {}),
      past: [...past, { notes: song.notes, locked, techniques }], future: future.slice(1), saveState: 'dirty',
    })
    scheduleSave(get)
    scheduleRegen(get)
  },
  replaceSong: (song) => {
    set({ song, past: [], future: [], saveState: 'saved', selectedNoteId: null, tabSel: [] })
    scheduleRegen(get)
  },
  requestFocus: (t) => set((s) => ({ focus: { t, n: (s.focus?.n ?? 0) + 1 } })),

  saveNow: async () => {
    clearTimeout(saveTimer)
    const { song, currentId, tab, tabSettings, locked, techniques } = get()
    if (!song || !currentId) return
    set({ saveState: 'saving' })
    try {
      await api.saveSong(currentId, song)
      if (tab) await api.saveTab(currentId, { settings: tabSettings, events: tab.events, summary: tab.summary, locked, techniques })
      set({ saveState: get().song === song ? 'saved' : 'dirty' })
    } catch (e) {
      set({ saveState: 'error', error: `บันทึกไม่สำเร็จ: ${e instanceof Error ? e.message : e}` })
    }
  },

  setTabSettings: (patch) => {
    set((s) => ({ tabSettings: { ...s.tabSettings, ...patch }, saveState: 'dirty' }))
    // ตั้งค่าแทปใหม่ = สร้างแทปให้ทันที (แม้ยังไม่เคยสร้าง เพราะผู้ใช้กำลังขอดูผลของค่านั้น)
    clearTimeout(regenTimer)
    regenTimer = window.setTimeout(() => void get().regenerateTab(), 150)
    scheduleSave(get)
  },

  regenerateTab: async () => {
    const { song, currentId, tabSettings, locked, techniques } = get()
    if (!song || !currentId) return
    const seq = ++regenSeq
    set({ tabBusy: true })
    try {
      const res = await api.generateTab(currentId, tabSettings, locked, song.notes)
      if (seq !== regenSeq) return // มีคำขอใหม่กว่าแล้ว ทิ้งผลเก่า
      const events = res.events.map((e) => ({ ...e, techniques: techniques[e.note_id] ?? {} }))
      set((st) => ({ tab: { events, summary: res.summary }, tabBusy: false, tabVersion: st.tabVersion + 1 }))
      scheduleSave(get)
    } catch (e) {
      if (seq === regenSeq) set({ tabBusy: false, error: `สร้างแทปไม่สำเร็จ: ${e instanceof Error ? e.message : e}` })
    }
  },

  setError: (error) => set({ error }),
  setView: (v) => set((s) => ({ view: { ...s.view, ...v } })),
  selectNote: (selectedNoteId) => set({ selectedNoteId, tabSel: selectedNoteId ? [selectedNoteId] : [] }),
  toggleTabSel: (id) =>
    set((s) => {
      const has = s.tabSel.includes(id)
      const tabSel = has ? s.tabSel.filter((x) => x !== id) : [...s.tabSel, id]
      return { tabSel, selectedNoteId: has ? (tabSel[tabSel.length - 1] ?? null) : id }
    }),

  refreshProjects: async () => {
    try {
      set({ projects: await api.listProjects() })
    } catch (e) {
      set({ error: String(e) })
    }
  },

  openProject: async (id) => {
    try {
      const p = await api.getProject(id)
      let f0: F0Curve | null = null
      let tab: TabData | null = null
      let tabSettings = DEFAULT_TAB_SETTINGS
      let locked: Record<string, FretPos> = {}
      let techniques: Record<string, Techniques> = {}
      if (p.song) {
        try { f0 = await api.getF0(id) } catch { /* ยังไม่มี f0 */ }
        try {
          const t = await api.getTab(id)
          if (t.settings && t.events && t.summary) {
            tabSettings = { ...DEFAULT_TAB_SETTINGS, ...t.settings }
            locked = t.locked ?? {}
            techniques = (t.techniques as Record<string, Techniques>) ?? {}
            if (!(tabSettings.tuning in TUNINGS)) tabSettings.tuning = 'standard'
            tab = { events: t.events.map((e) => ({ ...e, techniques: techniques[e.note_id] ?? {} })), summary: t.summary }
          }
        } catch { /* ยังไม่มีแทป */ }
      }
      clearTimeout(regenTimer)
      regenSeq++
      set({
        currentId: id, song: p.song, f0, tab, tabSettings, locked, techniques, selectedNoteId: null, tabSel: [], error: null,
        past: [], future: [], saveState: 'saved',
      })
      // แทปเก่าที่โน้ตเปลี่ยนไปแล้ว (จำนวนไม่ตรง) สร้างใหม่ให้อัตโนมัติ
      if (tab && p.song && tab.events.length !== p.song.notes.length) void get().regenerateTab()
    } catch (e) {
      set({ error: `เปิดโปรเจกต์ไม่สำเร็จ: ${e instanceof Error ? e.message : e}` })
    }
  },

  closeProject: () => {
    void get().saveNow() // กันงานแก้ไขหายตอนกลับหน้ารวมโปรเจกต์
    clearTimeout(regenTimer)
    regenSeq++
    set({ currentId: null, song: null, f0: null, selectedNoteId: null, tabSel: [], past: [], future: [], tab: null, locked: {}, techniques: {} })
  },

  connect: () => {
    let ws: WebSocket | null = null
    let closed = false
    let retry: number | undefined
    const open = () => {
      ws = new WebSocket(wsUrl())
      ws.onopen = () => set({ connected: true, lastHeartbeat: Date.now() })
      ws.onclose = () => {
        set({ connected: false })
        if (!closed) retry = window.setTimeout(open, 1500)
      }
      ws.onmessage = (m) => {
        const e = JSON.parse(m.data)
        const s = get()
        switch (e.type) {
          case 'hello': {
            const jobs: Record<string, JobInfo> = {}
            for (const j of e.jobs as JobInfo[]) jobs[j.id] = j
            set({ jobs, lastHeartbeat: Date.now() })
            break
          }
          case 'heartbeat':
            set({ lastHeartbeat: Date.now() })
            break
          case 'system.stats':
            set({ stats: e as SystemStats, lastHeartbeat: Date.now() })
            break
          case 'job.queued':
            set({
              jobs: {
                ...s.jobs,
                [e.job_id]: {
                  id: e.job_id, project_id: e.project_id, params: { karaoke: false, dereverb: false },
                  status: 'queued', overall_pct: 0, stage: null, error: null, elapsed_s: 0,
                },
              },
              stageRows: { ...s.stageRows, [e.job_id]: [] },
            })
            break
          case 'job.stage': {
            const ev = e as StageEvent
            const job = s.jobs[ev.job_id]
            const rows = [...(s.stageRows[ev.job_id] ?? [])]
            const i = rows.findIndex((r) => r.stage === ev.stage)
            const row: StageRow = { stage: ev.stage, status: ev.status, seconds: ev.seconds }
            if (i >= 0) rows[i] = row
            else rows.push(row)
            set({
              stageRows: { ...s.stageRows, [ev.job_id]: rows },
              jobs: job
                ? { ...s.jobs, [ev.job_id]: { ...job, status: 'running', stage: ev.stage, overall_pct: ev.overall_pct } }
                : s.jobs,
            })
            break
          }
          case 'job.done':
          case 'job.error':
          case 'job.cancelled': {
            const job = s.jobs[e.job_id]
            if (job) {
              set({
                jobs: {
                  ...s.jobs,
                  [e.job_id]: {
                    ...job,
                    status: e.type === 'job.done' ? 'done' : e.type === 'job.error' ? 'error' : 'cancelled',
                    overall_pct: e.type === 'job.done' ? 100 : job.overall_pct,
                    error: e.message ?? null,
                  },
                },
              })
            }
            if (e.type === 'job.error') set({ error: `งานวิเคราะห์ล้มเหลว: ${e.message}` })
            void get().refreshProjects()
            if (e.type === 'job.done' && get().currentId === e.project_id) void get().openProject(e.project_id)
            break
          }
        }
      }
    }
    open()
    return () => {
      closed = true
      clearTimeout(retry)
      ws?.close()
    }
  },
}))
