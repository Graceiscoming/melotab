import type { Beat, Note } from '../types'
import { midiToHz } from '../theory/notes'
import { timeStretch } from './stretch'

export type TrackName = 'mix' | 'vocals' | 'instrumental' | 'lead' | 'backing' | 'lead_dry'

/**
 * Transport บน Web Audio clock: เพลง (stem ที่เลือก) + synth ของโน้ตที่แกะได้ + metronome ตาม beat grid จริง
 * ทุกอย่างอ้างอิง ctx.currentTime เดียวกัน → sync ไม่ drift (schedule ล่วงหน้า ~120 ms)
 * slow-down: ใช้ buffer ที่ยืดเวลาด้วย SoundTouch (cache ต่อ stem+ความเร็ว) เวลาเพลง = เวลา ctx × rate
 * count-in: คลิก N จังหวะก่อนเพลงเริ่ม (ตามความเร็ว beat ณ จุดเริ่ม)
 */
export class Transport {
  ctx = new AudioContext()
  private buffers = new Map<string, AudioBuffer>()
  private srcs: AudioBufferSourceNode[] = []
  private musicGain = this.ctx.createGain()
  private musicPan = this.ctx.createStereoPanner()
  private synthGain = this.ctx.createGain()
  private synthPan = this.ctx.createStereoPanner()
  private clickGain = this.ctx.createGain()
  private vocalGain = this.ctx.createGain()
  private instGain = this.ctx.createGain()
  mixerOn = false // มิกเซอร์: เล่น stem เสียงร้อง + ดนตรี แยกกันเพื่อปรับระดับเสียงแต่ละส่วน

  track: TrackName = 'mix'
  playing = false
  private offset = 0 // ตำแหน่งในเพลง (วินาที) ตอนหยุด / ตอนเริ่มเล่น
  private startedAt = 0 // ctx.currentTime ตอนเริ่มเล่น
  duration = 0
  loop: { a: number; b: number } | null = null
  rate = 1 // ความเร็วเล่น (0.5–1.25)
  countIn = 0 // จำนวนจังหวะนับก่อนเริ่มเล่น
  stretched = new Map<string, AudioBuffer>()

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
    this.vocalGain.connect(this.musicGain)
    this.instGain.connect(this.musicGain)
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

  /** โหลด stem เข้าหน่วยความจำ (ไม่เปลี่ยน stem ที่เลือกเล่น) */
  async ensureLoaded(name: TrackName, url: string): Promise<void> {
    if (this.buffers.has(name)) return
    const res = await fetch(url)
    if (!res.ok) throw new Error(`โหลดเสียง ${name} ไม่สำเร็จ (${res.status})`)
    this.buffers.set(name, await this.ctx.decodeAudioData(await res.arrayBuffer()))
  }

  /** stem ที่จะเล่นจริง: โหมดมิกเซอร์ = เสียงร้อง (lead ถ้ามี) + instrumental แยกกัน (ถ้าโหลดครบ) ไม่งั้นเล่น stem ที่เลือก */
  private playNames(): { name: TrackName; bus: GainNode | null }[] {
    if (this.mixerOn) {
      const v: TrackName | null = this.buffers.has('lead') ? 'lead' : this.buffers.has('vocals') ? 'vocals' : null
      if (v && this.buffers.has('instrumental')) return [{ name: v, bus: this.vocalGain }, { name: 'instrumental', bus: this.instGain }]
    }
    return [{ name: this.track, bus: null }]
  }
  setMixer(on: boolean) {
    if (this.mixerOn === on) return
    this.mixerOn = on
    if (this.rate !== 1) void this.setRate(this.rate)
    else if (this.playing) void this.play(this.getTime())
  }
  setVocalVolume(v: number) { this.vocalGain.gain.value = v }
  setInstVolume(v: number) { this.instGain.gain.value = v }

  async loadTrack(name: TrackName, url: string): Promise<void> {
    await this.ensureLoaded(name, url)
    this.track = name
    this.duration = this.buffers.get(name)!.duration
    if (this.rate !== 1) await this.setRate(this.rate) // เตรียม buffer ยืดเวลาของ stem ใหม่ (เล่นต่อให้เองถ้ากำลังเล่น)
    else if (this.playing) void this.play(this.getTime()) // เปลี่ยน stem ระหว่างเล่น: เล่นต่อจากตำแหน่งเดิม
  }

  clearTracks() {
    this.pause()
    this.buffers.clear()
    this.stretched.clear()
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
    const t = this.playing ? this.offset + Math.max(0, this.ctx.currentTime - this.startedAt) * this.rate : this.offset
    return Math.max(0, this.duration ? Math.min(t, this.duration) : t)
  }

  async play(from = this.offset, withCountIn = false) {
    await this.ctx.resume()
    this.stopSource()
    const names = this.playNames()
    const origs = names.map((n) => this.buffers.get(n.name))
    if (origs.some((o) => !o)) return
    const orig = origs[0]!
    const stretchedAll = names.map((n) => this.stretched.get(`${n.name}@${this.rate}`))
    if (this.rate !== 1 && stretchedAll.some((x) => !x)) this.rate = 1 // ยังไม่มี buffer ที่ยืดไว้ → เล่นปกติ (setRate เป็นคนเตรียม buffer)
    const r = this.rate
    from = Math.max(0, Math.min(from, orig.duration - 0.01))
    const lead = withCountIn ? this.countInClicks(from) : 0
    this.startedAt = this.ctx.currentTime + 0.03 + lead // เผื่อเวลาเริ่ม ให้ schedule ทัน (+ เวลานับ)
    names.forEach((n, i) => {
      const s = this.ctx.createBufferSource()
      s.buffer = r === 1 ? origs[i]! : stretchedAll[i]!
      s.connect(n.bus ?? this.musicGain)
      if (i === 0) {
        s.onended = () => {
          if (this.srcs[0] === s && this.playing && this.getTime() >= orig.duration - 0.05) this.pause(true)
        }
      }
      s.start(this.startedAt, from / r)
      this.srcs.push(s)
    })
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
    for (const src of this.srcs) {
      src.onended = null
      try { src.stop() } catch { /* หยุดไปแล้ว */ }
      src.disconnect()
    }
    this.srcs = []
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
    const horizon = now + 0.12 * this.rate
    const toCtx = (songTime: number) => this.startedAt + (songTime - this.offset) / this.rate
    while (this.noteIdx < this.notes.length && this.notes[this.noteIdx].start < horizon) {
      const n = this.notes[this.noteIdx++]
      if (this.synthOn && n.start >= now - 0.02) this.blip(midiToHz(n.midi + this.noteTranspose), toCtx(n.start), Math.max(0.06, (n.end - n.start) / this.rate))
    }
    while (this.beatIdx < this.beats.length && this.beats[this.beatIdx].time + this.clickOffset < horizon) {
      const b = this.beats[this.beatIdx++]
      if (this.clickOn && b.time + this.clickOffset >= now - 0.02) this.click(toCtx(b.time + this.clickOffset), b.beat === 1)
    }
  }

  /** เสียงเปียโนสังเคราะห์ 1 โน้ต: partial หลายตัวที่ decay ตามระดับเสียง (โน้ตสูงจางเร็ว) + ปล่อยเสียงเมื่อโน้ตจบ */
  private blip(hz: number, when: number, dur: number) {
    const t = Math.max(when, this.ctx.currentTime)
    const decay = Math.max(0.35, Math.min(2.2, 2.4 * Math.pow(220 / hz, 0.6)))   // วินาทีที่เสียงลดลง ~60 dB
    const hold = Math.max(0.12, dur)
    const g = this.ctx.createGain()
    g.gain.setValueAtTime(0, t)
    g.gain.linearRampToValueAtTime(0.9, t + 0.006)
    g.gain.setTargetAtTime(0.0001, t + 0.006, decay / 6.9)                          // เสียงค่อย ๆ จาง (เหมือนสายเปียโน)
    g.gain.setTargetAtTime(0, t + hold, 0.07)                                       // ปล่อยคีย์เมื่อโน้ตจบ
    g.connect(this.synthGain)
    const partials: [number, number, number][] = [[1, 1, 1], [2, 0.5, 1.6], [3, 0.28, 2.2], [4, 0.14, 3], [5, 0.07, 4]] // [ตัวคูณความถี่, แอมพลิจูด, ความเร็วจางสัมพัทธ์]
    const stopAt = t + hold + 0.5
    for (const [mult, amp, fast] of partials) {
      if (hz * mult > 9000) continue
      const o = this.ctx.createOscillator()
      const og = this.ctx.createGain()
      o.type = 'sine'
      o.frequency.value = hz * mult * (1 + 0.0004 * mult * mult)                    // inharmonicity เล็กน้อย
      og.gain.setValueAtTime(amp, t)
      og.gain.setTargetAtTime(amp * 0.05, t, decay / (6.9 * fast))
      o.connect(og).connect(g)
      o.start(t)
      o.stop(stopAt)
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

  /** ตั้งความเร็ว: เตรียม buffer ยืดเวลา (ครั้งแรกใช้เวลาหลายวินาที) แล้วเล่นต่อจากตำแหน่งเดิม */
  async setRate(rate: number, onBusy?: (busy: boolean) => void) {
    if (rate !== 1) {
      const todo = this.playNames().filter((n) => !this.stretched.has(`${n.name}@${rate}`))
      if (todo.length) {
        onBusy?.(true)
        try {
          for (const n of todo) {
            const orig = this.buffers.get(n.name)
            if (orig) this.stretched.set(`${n.name}@${rate}`, await timeStretch(this.ctx, orig, rate))
          }
        } finally { onBusy?.(false) }
      }
    }
    const t = this.getTime()
    const was = this.playing
    this.rate = rate
    if (was) await this.play(t)
    else this.offset = t
  }

  /** นับจังหวะก่อนเริ่ม: วางคลิกล่วงหน้า คืนความยาวช่วงนับ (วินาที ctx) */
  private countInClicks(from: number): number {
    if (this.countIn <= 0) return 0
    const bs = this.beats
    const i = Math.max(0, Math.min(this.lowerBound(bs.map((b) => b.time), from), bs.length - 2))
    const period = bs.length > 1 ? Math.max(0.2, bs[i + 1].time - bs[i].time) / this.rate : 0.5
    const t0 = this.ctx.currentTime + 0.03
    for (let k = 0; k < this.countIn; k++) this.click(t0 + k * period, k === 0)
    return this.countIn * period
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
