import type { Alternative, BlocksResponse, Block, F0Curve, FretPos, JobInfo, KeySuggestion, Note, ProjectFull, ProjectMeta, Song, TabResult, TabSettings } from '../types'
import type { TechSuggestion } from '../tab/ops'

export const API = (import.meta.env.VITE_API as string | undefined) ?? 'http://localhost:8000'

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    try { msg = (await res.json()).detail ?? msg } catch { /* ไม่ใช่ JSON */ }
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return res.json() as Promise<T>
}

const post = (path: string, body?: unknown) =>
  fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) })

export const api = {
  listProjects: () => fetch(API + '/projects').then(j<ProjectMeta[]>),
  getProject: (id: string) => fetch(`${API}/projects/${encodeURIComponent(id)}`).then(j<ProjectFull>),
  getF0: (id: string) => fetch(`${API}/projects/${encodeURIComponent(id)}/f0`).then(j<F0Curve>),
  upload: (file: File, title?: string) => {
    const fd = new FormData()
    fd.append('file', file)
    if (title) fd.append('title', title)
    return fetch(API + '/projects/upload', { method: 'POST', body: fd }).then(j<ProjectMeta>)
  },
  analyze: (id: string, opts: { karaoke: boolean; dereverb: boolean }) =>
    post(`/projects/${encodeURIComponent(id)}/analyze`, opts).then(j<JobInfo>),
  cancel: (jobId: string) => post(`/jobs/${jobId}/cancel`).then(j<JobInfo>),
  saveSong: (id: string, song: Song) =>
    fetch(`${API}/projects/${encodeURIComponent(id)}/song`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(song),
    }).then(j<{ ok: boolean; notes: number }>),
  retranscribe: (id: string, opts: { fix_octave: boolean; min_dur_ms: number; merge_gap_ms: number }) =>
    post(`/projects/${encodeURIComponent(id)}/retranscribe`, opts).then(j<Song>),
  history: (id: string) => fetch(`${API}/projects/${encodeURIComponent(id)}/history`).then(j<string[]>),
  restore: (id: string, name: string) => post(`/projects/${encodeURIComponent(id)}/history/${name}/restore`).then(j<Song>),
  getTab: (id: string) => fetch(`${API}/projects/${encodeURIComponent(id)}/tab`).then(j<Partial<TabResult> & { techniques?: Record<string, unknown> }>),
  saveTab: (id: string, tab: unknown) =>
    fetch(`${API}/projects/${encodeURIComponent(id)}/tab`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(tab) }).then(j<{ ok: boolean }>),
  generateTab: (id: string, settings: TabSettings, locked: Record<string, FretPos>, notes: Note[]) =>
    post(`/projects/${encodeURIComponent(id)}/tab/generate`, { settings, locked, notes }).then(j<TabResult>),
  alternatives: (id: string, noteId: string, settings: TabSettings, locked: Record<string, FretPos>, notes: Note[]) =>
    post(`/projects/${encodeURIComponent(id)}/tab/alternatives`, { note_id: noteId, settings, locked, notes }).then(j<Alternative[]>),
  exportProject: (id: string, body: unknown) => post(`/projects/${encodeURIComponent(id)}/export`, body).then(j<{ dir: string; files: { name: string; size: number; format: string }[]; skipped: { format: string; reason: string }[] }>),
  batch: (body: { paths: string[]; folder: string | null; options: { karaoke: boolean; dereverb: boolean } }) =>
    post('/batch', body).then(j<{ created: { project: ProjectMeta }[]; errors: { path: string; error: string }[] }>),
  models: () => fetch(`${API}/models`).then(j<{ models: { id: string; name: string; role: string; present: boolean; size_bytes: number; vram_gb: number; required: boolean; deletable: boolean }[]; total_bytes: number; disk_free_bytes: number; models_dir: string }>),
  deleteModel: (id: string) => fetch(`${API}/models/${encodeURIComponent(id)}`, { method: 'DELETE' }).then(j<{ freed_bytes: number }>),
  harmony: (id: string, body: { interval: string; direction: string; settings: TabSettings }) =>
    post(`/projects/${encodeURIComponent(id)}/harmony`, body).then(j<{ notes: Note[]; tab: TabResult; text: string }>),
  autoTechniques: (id: string, settings: TabSettings, locked: Record<string, FretPos>, notes: Note[]) =>
    post(`/projects/${encodeURIComponent(id)}/tab/techniques/auto`, { settings, locked, notes }).then(j<TechSuggestion>),
  blocks: (id: string, body: { system: string; transpose: number; capo: number; tuning: string; selected: Block[]; notes: Note[] }) =>
    post(`/projects/${encodeURIComponent(id)}/tab/blocks`, body).then(j<BlocksResponse>),
  suggestKeys: (id: string, settings: Partial<TabSettings>, notes: Note[]) =>
    post(`/projects/${encodeURIComponent(id)}/keys/suggest`, { settings, notes }).then(j<KeySuggestion>),
  lyrics: (id: string, opts: { model_size: string; language: string | null; text: string | null; force_asr: boolean }) =>
    post(`/projects/${encodeURIComponent(id)}/lyrics`, opts).then(j<JobInfo>),
  lyricsAlign: (id: string, text: string) => post(`/projects/${encodeURIComponent(id)}/lyrics/align`, { text }).then(j<unknown>),
  audioUrl: (id: string, stem: string) => `${API}/audio/${encodeURIComponent(id)}/${stem}`,
}

export function wsUrl(): string { return API.replace(/^http/, 'ws') + '/ws' }
