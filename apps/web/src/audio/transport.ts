import type { Beat, Note } from '../types'
import { midiToHz } from '../theory/notes'

export type TrackName = 'mix' | 'vocals' | 'instrumental' | 'lead' | 'backing' | 'lead_dry'

/**
 * Transport บน Web Audio clock: เพลง (stem ที่เลือก) + synth ของโน้ตที่แกะได้ + metronome ตาม beat grid จริง
 * ทุกอย่างอ้างอิง ctx.currentTime เดียวกัน → sync ไม่ drift (schedule ล่วงหน้า ~120 ms)
 * ยังไม่มี slow-down แบบไม่เพี้ยนเสียง (ทำในขั้น practice tools)
 */
export class Transport {
  ctx = new AudioContext()
  private buffers = new Map<string, AudioBuffer>()
  private src: AudioBufferSourceNode | null = null
  private musicGain = this.ctx.createGain()
  private musicPan = this.ctx.createStereoPanner()
  private synthGain = this.ctx.createGain()
  private synthPan = this.ctx.createStereoPanner()
  private clickGain = this.ctx.createGain()

  track: TrackName = 'mix'
  playing = false
  private offset = 0 // ตำแหน่งในเพลง (วินาที) ตอนหยุด / ตอนเริ่มเล่น
  private startedAt = 0 // ctx.currentTime ตอนเริ่มเล่น
  duration = 0
  loop: { a: number; b: number } | null = null

  private notes: Note[] = []
  private beats: Beat[] = []
  private noteIdx = 0
  private beatIdx = 0
  private timer: number | null = null
  synthOn = false
  clickOn = false
  clickOffset = 0 // วินาที ชดเชย latency (หูฟัง bluetooth)
  noteTranspose = 0 // semitone: ให้ synth โน้ตเล่นตามคีย์ที่ยกในแทป (ฟังแทปที่เล่นจริง)
  onEnded: (() => void) | null = null

  constructor() {
    this.musicGain.connect(this.musicPan).connect(this.ctx.destination)
    this.synthGain.connect(this.synthPan).connect(this.ctx.destination)
    this.clickGain.connect(this.ctx.destination)
    this.synthGain.gain.value = 0.35
    this.clickGain.gain.value = 0.5
  }

  setSong(notes: Note[], beats: Beat[]) {
    this.notes = [...notes].sort((a, b) => a.start - b.start)
    this.beats = beats
    this.resetCursors(this.getTime())
  }

  async loadTrack(name: TrackName, url: string): Promise<void> {
    if (!this.buffers.has(name)) {
      const res = await fetch(url)
      if (!res.ok) throw new Error(`โหลดเสียง ${name} ไม่สำเร็จ (${res.status})`)
      this.buffers.set(name, await this.ctx.decodeAudioData(await res.arrayBuffer()))
    }
    this.track = name
    this.duration = this.buffers.get(name)!.duration
    if (this.playing) void this.play(this.getTime()) // เปลี่ยน stem ระหว่างเล่น: เล่นต่อจากตำแหน่งเดิม
  }

  clearTracks() {
    this.pause()
    this.buffers.clear()
    this.offset = 0
    this.duration = 0
  }

  /** โหมดฟังเทียบ: เพลงออกซ้าย / synth โน้ตออกขวา */
  setSplit(on: boolean) {
    this.musicPan.pan.value = on ? -1 : 0
    this.synthPan.pan.value = on ? 1 : 0
  }
  setMusicVolume(v: number) { this.musicGain.gain.value = v }
  setSynthVolume(v: number) { this.synthGain.gain.value = v }
  setClickVolume(v: number) { this.clickGain.gain.value = v }

  getTime(): number {
    const t = this.playing ? this.offset + (this.ctx.currentTime - this.startedAt) : this.offset
    return Math.max(0, this.duration ? Math.min(t, this.duration) : t)
  }

  async play(from = this.offset) {
    await this.ctx.resume()
    this.stopSource()
    const buf = this.buffers.get(this.track)
    if (!buf) return
    from = Math.max(0, Math.min(from, buf.duration - 0.01))
    const s = this.ctx.createBufferSource()
    s.buffer = buf
    s.connect(this.musicGain)
    s.onended = () => {
      if (this.src === s && this.playing && this.getTime() >= buf.duration - 0.05) this.pause(true)
    }
    this.startedAt = this.ctx.currentTime + 0.03 // เผื่อเวลาเริ่ม ให้ schedule ทัน
    s.start(this.startedAt, from)
    this.src = s
    this.offset = from
    this.playing = true
    this.resetCursors(from)
    if (this.timer === null) this.timer = window.setInterval(() => this.schedule(), 25)
    this.schedule()
  }

  pause(ended = false) {
    this.offset = ended ? 0 : this.getTime()
    this.playing = false
    this.stopSource()
    if (this.timer !== null) {
      clearInterval(this.timer)
      this.timer = null
    }
    if (ended) this.onEnded?.()
  }

  seek(t: number) {
    t = Math.max(0, this.duration ? Math.min(t, this.duration) : t)
    if (this.playing) void this.play(t)
    else {
      this.offset = t
      this.resetCursors(t)
    }
  }

  private stopSource() {
    if (this.src) {
      this.src.onended = null
      try { this.src.stop() } catch { /* หยุดไปแล้ว */ }
      this.src.disconnect()
      this.src = null
    }
  }

  private resetCursors(t: number) {
    this.noteIdx = this.lowerBound(this.notes.map((n) => n.start), t - 0.001)
    this.beatIdx = this.lowerBound(this.beats.map((b) => b.time + this.clickOffset), t - 0.001)
  }

  private lowerBound(arr: number[], v: number) {
    let lo = 0
    let hi = arr.length
    while (lo < hi) {
      const m = (lo + hi) >> 1
      if (arr[m] < v) lo = m + 1
      else hi = m
    }
    return lo
  }

  private schedule() {
    if (!this.playing) return
    const now = this.getTime()
    if (this.loop && now >= this.loop.b) {
      void this.play(this.loop.a)
      return
    }
    const horizon = now + 0.12
    const toCtx = (songTime: number) => this.startedAt + (songTime - this.offset)
    while (this.noteIdx < this.notes.length && this.notes[this.noteIdx].start < horizon) {
      const n = this.notes[this.noteIdx++]
      if (this.synthOn && n.start >= now - 0.02) this.blip(midiToHz(n.midi + this.noteTranspose), toCtx(n.start), Math.max(0.06, n.end - n.start))
    }
    while (this.beatIdx < this.beats.length && this.beats[this.beatIdx].time + this.clickOffset < horizon) {
      const b = this.beats[this.beatIdx++]
      if (this.clickOn && b.time + this.clickOffset >= now - 0.02) this.click(toCtx(b.time + this.clickOffset), b.beat === 1)
    }
  }

  /** เสียง synth โน้ตเดียว (สามเหลี่ยม + harmonic เบา ๆ ให้ได้ยินชัดซ้อนกับเสียงร้อง) */
  private blip(hz: number, when: number, dur: number) {
    const t = Math.max(when, this.ctx.currentTime)
    const g = this.ctx.createGain()
    g.gain.setValueAtTime(0, t)
    g.gain.linearRampToValueAtTime(0.5, t + 0.01)
    g.gain.setValueAtTime(0.5, t + Math.max(0.01, dur - 0.03))
    g.gain.linearRampToValueAtTime(0, t + dur)
    g.connect(this.synthGain)
    for (const [mult, amp] of [[1, 1], [2, 0.3]] as const) {
      const o = this.ctx.createOscillator()
      const og = this.ctx.createGain()
      o.type = 'triangle'
      o.frequency.value = hz * mult
      og.gain.value = amp
      o.connect(og).connect(g)
      o.start(t)
      o.stop(t + dur + 0.02)
    }
  }

  private click(when: number, down: boolean) {
    const t = Math.max(when, this.ctx.currentTime)
    const o = this.ctx.createOscillator()
    const g = this.ctx.createGain()
    o.frequency.value = down ? 1800 : 1100
    g.gain.setValueAtTime(down ? 0.9 : 0.55, t)
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.05)
    o.connect(g).connect(this.clickGain)
    o.start(t)
    o.stop(t + 0.06)
  }

  /** ฟังโน้ตเดียว (คลิกบน piano roll) */
  audition(midi: number, dur = 0.4) {
    void this.ctx.resume().then(() => this.blip(midiToHz(midi), this.ctx.currentTime, dur))
  }

  dispose() {
    this.pause()
    void this.ctx.close()
  }
}
