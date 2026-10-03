export interface Note {
  id: string
  midi: number
  name: string
  freq: number
  start: number
  end: number
  start_beat?: number
  dur_beats?: number
  start_beat_q?: number
  dur_beats_q?: number
  cents_offset: number | null
  confidence: number
  octave_suspect: boolean
  octave_fixed?: boolean
  edited: boolean
}

export interface Beat { time: number; bar: number; beat: number }

export interface KeyInfo {
  tonic: string
  mode: 'major' | 'minor'
  score: number
  alternatives: { tonic: string; mode: string; score: number }[]
}

export interface Song {
  version: number
  tuning_offset_cents?: number
  source: { title: string; duration: number; audio_hash: string; path?: string }
  key: KeyInfo | null
  tempo: { bpm: number | null; bpm_raw_median: number | null; unstable: boolean | null }
  time_signature: { num: number; den: number } | null
  beats: Beat[]
  notes: Note[]
  f0_ref: string | null
  meta: { karaoke: boolean; dereverb: boolean; melody_source: string; timings_s: Record<string, number>; cached_stages: string[]; fix_octave?: boolean; min_dur_ms?: number; merge_gap_ms?: number }
  [extra: string]: unknown
}

export interface ProjectMeta { id: string; title: string; source_file: string; created: number; analyzed?: boolean }
export interface ProjectFull extends ProjectMeta { song: Song | null }
export interface F0Curve { hop_s: number; t0: number; midi: (number | null)[] }

export interface JobInfo {
  id: string; project_id: string; params: { karaoke: boolean; dereverb: boolean }
  status: 'queued' | 'running' | 'done' | 'error' | 'cancelled'
  overall_pct: number; stage: string | null; error: string | null; elapsed_s: number
}

export interface StageEvent {
  type: 'job.stage'; job_id: string; stage: string; stage_index: number; stage_total: number
  status: 'start' | 'done' | 'cached'; seconds?: number; overall_pct: number
}

export interface SystemStats {
  cpu_pct: number; ram_used_gb: number; ram_total_gb: number
  gpu: { name: string; util_pct: number; vram_used_gb: number; vram_total_gb: number; temp_c: number } | null
}
