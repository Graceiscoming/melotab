import { create } from 'zustand'
import { api, wsUrl } from '../api/client'
import type { F0Curve, JobInfo, ProjectMeta, Song, StageEvent, SystemStats } from '../types'

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
}

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

  refreshProjects: () => Promise<void>
  openProject: (id: string) => Promise<void>
  closeProject: () => void
  setError: (e: string | null) => void
  setView: (v: Partial<View>) => void
  selectNote: (id: string | null) => void
  connect: () => () => void
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
  view: { showF0: true, highlightKey: true, follow: true, pxPerSec: 90, labels: true },
  selectedNoteId: null,

  setError: (error) => set({ error }),
  setView: (v) => set((s) => ({ view: { ...s.view, ...v } })),
  selectNote: (selectedNoteId) => set({ selectedNoteId }),

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
      if (p.song) {
        try { f0 = await api.getF0(id) } catch { /* ยังไม่มี f0 */ }
      }
      set({ currentId: id, song: p.song, f0, selectedNoteId: null, error: null })
    } catch (e) {
      set({ error: `เปิดโปรเจกต์ไม่สำเร็จ: ${e instanceof Error ? e.message : e}` })
    }
  },

  closeProject: () => set({ currentId: null, song: null, f0: null, selectedNoteId: null }),

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
