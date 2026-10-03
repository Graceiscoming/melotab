import type { F0Curve, JobInfo, ProjectFull, ProjectMeta, Song } from '../types'

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
  audioUrl: (id: string, stem: string) => `${API}/audio/${encodeURIComponent(id)}/${stem}`,
}

export function wsUrl(): string { return API.replace(/^http/, 'ws') + '/ws' }
