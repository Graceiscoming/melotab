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

export interface Chord {
  start_beat: number; end_beat: number; start: number; end: number
  symbol: string              // เช่น "Bm7", "C/E" ("N" = ไม่มีคอร์ด)
  root: number | null         // 0..11 (C = 0)
  quality: string | null
  bass: string | null
  confidence: number | null   // BTC ไม่ให้ค่านี้ → null เสมอ
  edited?: boolean
}
export interface Section { id: string; label: string; start_bar: number; end_bar: number; start: number; end: number; auto: boolean }
export interface KeyChange { time: number; bar: number; tonic: string; mode: string; score: number }
export interface LyricWord { text: string; start: number; end: number; note_ids?: string[] }
export interface LyricLine { id: string; start: number; end: number; text: string; words: LyricWord[] }
export interface Lyrics { language: string | null; source: 'asr' | 'pasted'; model?: string | null; text?: string | null; aligned_with_asr?: boolean; lines: LyricLine[] }

export interface Song {
  chords?: Chord[]
  sections?: Section[]
  key_changes?: KeyChange[]
  lyrics?: Lyrics
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

// ---------------- Guitar Tab (Phase 3) ----------------
export interface Block {
  id: string
  label: string
  system: 'position' | 'pentatonic' | 'custom'
  fret_min: number
  fret_max: number
  pcs: number[]
}

export type TabWarning = 'hard_shift' | 'stretch' | 'unplayable' | 'out_of_block' | 'octave_shifted'

export interface Techniques {
  in?: string          // slide_in | grace
  on?: string[]        // vibrato | bend | let_ring
  to_next?: string     // hammer | pull | slide
  [k: string]: unknown
}

export interface TabEvent {
  id: string
  note_id: string
  pitch: number
  string: number | null
  fret: number | null
  start: number
  end: number
  start_beat: number | null
  dur_beats: number | null
  techniques: Techniques
  bend: number | null
  finger: number | null
  locked: boolean
  difficulty: number
  warnings: TabWarning[]
  anchor?: number
  octave_shifted?: number
}

export interface TabSettings {
  transpose: number
  capo: number
  tuning: string
  max_fret: number
  blocks: Block[]
  block_mode: 'single' | 'multi'
  out_of_block: 'octave_shift' | 'stretch' | 'warn'
  preset: string
}

export interface TabSummary {
  notes: number; playable: number; total_cost: number; difficulty: number
  hard: number; unplayable: number; out_of_block: number; octave_shifted: number
}

export interface TabResult { settings: TabSettings; events: TabEvent[]; summary: TabSummary; locked?: Record<string, FretPos> }
export interface FretPos { string: number; fret: number }

export interface KeyOption {
  transpose: number; capo: number; kind: 'same_sound' | 'transposed'; shape_key: string; sounding_key: string
  score: number; difficulty: number; hard: number; unplayable: number; friendly: boolean
}
export interface KeySuggestion { original_key: string; same_sound: KeyOption[]; transposed: KeyOption[]; best: KeyOption | null }
export interface Alternative { string: number; fret: number; pitch: number; delta_cost: number; hard: number }
export interface BlocksResponse { tonic: string; mode: string; blocks: Block[]; coverage: number | null }
