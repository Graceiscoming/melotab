import type { TabEvent } from '../types'

export type NoteResult = 'hit' | 'miss' | 'octave'
export const CENTS_TOL = 50 // ยอมคลาดเคลื่อนจากพิทช์เป้าหมาย (± cents)
const EARLY = 0.08 // เริ่มนับได้ก่อนโน้ตเริ่มเล็กน้อย (วินาที)
const MIN_FRAMES = 2 // ต้องตรงอย่างน้อยกี่เฟรมถึงนับว่าเล่นถูก

/** ให้คะแนนการเล่นตามแทป (score following แบบง่าย): ทุกครั้งที่เฟรมเสียงมา เทียบกับโน้ตที่ควรเล่นอยู่ ณ เวลานั้น
 *  โน้ตผ่านพ้น (เวลา > end) แล้วจึงตัดสินเป็น hit/miss/octave (ตรงแต่คนละ octave) — ไม่ตัดสินโน้ตที่ยังไม่ถึง */
export class PracticeScorer {
  private frames = new Map<string, { hit: number; oct: number }>()
  results = new Map<string, NoteResult>()
  private cursor = 0
  private events: TabEvent[]
  constructor(events: TabEvent[]) { this.events = [...events].sort((a, b) => a.start - b.start) }

  update(t: number, detectedMidi: number | null): void {
    for (const e of this.events) {
      if (e.start - EARLY > t) break
      if (e.end < t || detectedMidi === null) continue
      const f = this.frames.get(e.id) ?? { hit: 0, oct: 0 }
      const diff = (detectedMidi - e.pitch) * 100
      if (Math.abs(diff) <= CENTS_TOL) f.hit++
      else if (Math.abs(((diff + 600) % 1200) - 600) <= CENTS_TOL) f.oct++ // ต่างกันเป็น octave พอดี
      this.frames.set(e.id, f)
    }
    while (this.cursor < this.events.length && this.events[this.cursor].end < t) {
      const e = this.events[this.cursor++]
      const f = this.frames.get(e.id)
      this.results.set(e.id, f && f.hit >= MIN_FRAMES ? 'hit' : f && f.oct >= MIN_FRAMES ? 'octave' : 'miss')
    }
  }

  reset(): void { this.frames.clear(); this.results.clear(); this.cursor = 0 }
  /** เริ่มใหม่จากเวลา t (เช่น seek/loop): โน้ตก่อน t ไม่นับ */
  seek(t: number): void {
    this.reset()
    while (this.cursor < this.events.length && this.events[this.cursor].end < t) this.cursor++
  }
  summary() {
    let hit = 0
    let miss = 0
    let oct = 0
    this.results.forEach((r) => { if (r === 'hit') hit++; else if (r === 'octave') oct++; else miss++ })
    const total = hit + miss + oct
    return { hit, miss, octave: oct, total, pct: total ? Math.round((hit / total) * 100) : 0 }
  }
}
