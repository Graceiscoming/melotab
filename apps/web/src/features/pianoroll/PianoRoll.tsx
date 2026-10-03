import { Application, BitmapText, Container, Graphics } from 'pixi.js'
import { useEffect, useRef } from 'react'
import { getTransport } from '../../audio/instance'
import { setPitch, setTimes, addNote } from '../../store/edits'
import { useStore } from '../../store/store'
import { snapTime } from '../../theory/rhythm'
import { preferFlats, spellChord } from '../../theory/chords'
import { BLACK, noteName, scalePcs } from '../../theory/notes'
import type { Note } from '../../types'

const KEY_W = 64
const RULER_H = 22
const SEC_H = 16 // แถบท่อน
const CH_H = 20 // แถบคอร์ด
const LY_H = 18 // แถบเนื้อร้อง
const STRIP_H = SEC_H + CH_H + LY_H
const TOP = RULER_H + STRIP_H // ขอบบนของพื้นที่โน้ต
const ROW_H = 16
const COLORS = {
  bg: 0x14161b, laneWhite: 0x1b1e25, laneBlack: 0x16181e, laneKey: 0x20283a, grid: 0x2a2f3a, bar: 0x434a5c,
  note: 0x5aa9ff, warn: 0xffa94d, sel: 0xffffff, f0: 0xffd666, ruler: 0x0f1115, key: 0xe8eaf0, keyBlack: 0x2b2f3a,
  playhead: 0xff5c7a, text: 0xcfd6e6,
}

/** แปลงตำแหน่ง (x,y) ในพื้นที่ canvas → เวลา/โน้ต */
export interface Viewport { scrollT: number; scrollY: number; minMidi: number; maxMidi: number; pxPerSec: number }

/** หาโน้ตที่ตรงจุดคลิก (เรียงตามเวลา ใช้การสแกนเชิงเส้น ~1000 โน้ตพอสำหรับคลิกครั้งเดียว) */
export function hitNote(notes: Note[], t: number, midi: number, pad = 0): Note | null {
  let best: Note | null = null
  for (const n of notes) {
    if (n.midi === midi && t >= n.start - pad && t <= n.end + pad) {
      if (!best || Math.abs(t - (n.start + n.end) / 2) < Math.abs(t - (best.start + best.end) / 2)) best = n
    }
  }
  return best
}

type DragMode = 'move' | 'left' | 'right'
const EDGE_PX = 6

export function PianoRoll() {
  const host = useRef<HTMLDivElement>(null)
  const song = useStore((s) => s.song)
  const f0 = useStore((s) => s.f0)
  const view = useStore((s) => s.view)
  const selectedId = useStore((s) => s.selectedNoteId)
  const stateRef = useRef({ song, f0, view, selectedId })
  stateRef.current = { song, f0, view, selectedId }
  const api = useRef<{ rebuild: () => void; scrollTo: (t: number) => void } | null>(null)
  const focus = useStore((s) => s.focus)

  useEffect(() => {
    let disposed = false
    let app: Application | null = null
    let cleanup = () => {}

    void (async () => {
      const el = host.current
      if (!el) return
      const a = new Application()
      await a.init({ resizeTo: el, background: COLORS.bg, antialias: true, resolution: window.devicePixelRatio || 1, autoDensity: true })
      if (disposed) { a.destroy(true); return }
      app = a
      el.appendChild(a.canvas)

      const worldX = new Container() // เลื่อนตามเวลา
      const body = new Container() // เลื่อนตามแนวตั้งด้วย
      worldX.addChild(body)
      const keys = new Container()
      const keysBody = new Container()
      keys.addChild(keysBody)
      const ruler = new Container()
      const playhead = new Graphics()
      a.stage.addChild(worldX, ruler, keys, playhead)

      const vp: Viewport = { scrollT: 0, scrollY: 0, minMidi: 48, maxMidi: 84, pxPerSec: 90 }
      let lastScale = 0
      let ghost = new Graphics()
      let strips: Container | null = null
      type Drag = { mode: DragMode; id: string; note: Note; x0: number; y0: number; moved: boolean; midi: number; start: number; end: number }
      let drag: Drag | null = null

      const timeToX = (t: number) => KEY_W + (t - vp.scrollT) * vp.pxPerSec
      const rowY = (midi: number) => TOP + (vp.maxMidi - midi) * ROW_H - vp.scrollY

      /** สร้างเนื้อหาใหม่ทั้งหมด (เมื่อ song/zoom/ตัวเลือกเปลี่ยน) */
      const rebuild = () => {
        const { song, f0, view, selectedId } = stateRef.current
        for (const c of [body, keysBody]) c.removeChildren().forEach((x) => x.destroy({ children: true }))
        vp.pxPerSec = view.pxPerSec
        if (!song || song.notes.length === 0) return
        const ms = song.notes.map((n) => n.midi)
        vp.minMidi = Math.min(...ms) - 3
        vp.maxMidi = Math.max(...ms) + 3
        const dur = song.source.duration + 2
        const W = dur * vp.pxPerSec
        const inKey = view.highlightKey ? scalePcs(song.key) : new Set<number>()

        const lanes = new Graphics()
        for (let m = vp.minMidi; m <= vp.maxMidi; m++) {
          const y = (vp.maxMidi - m) * ROW_H
          const pc = ((m % 12) + 12) % 12
          lanes.rect(0, y, W, ROW_H).fill(inKey.has(pc) ? COLORS.laneKey : BLACK.has(pc) ? COLORS.laneBlack : COLORS.laneWhite)
          if (pc === 0) lanes.rect(0, y + ROW_H - 1, W, 1).fill(COLORS.bar)
        }
        const H = (vp.maxMidi - vp.minMidi + 1) * ROW_H
        const grid = new Graphics()
        for (const b of song.beats) grid.rect(b.time * vp.pxPerSec, 0, b.beat === 1 ? 2 : 1, H).fill(b.beat === 1 ? COLORS.bar : COLORS.grid)
        body.addChild(lanes, grid)

        if (view.showF0 && f0) {
          const g = new Graphics()
          let open = false
          f0.midi.forEach((m, i) => {
            if (m === null || m < vp.minMidi - 1 || m > vp.maxMidi + 1) { open = false; return }
            const x = (f0.t0 + i * f0.hop_s) * vp.pxPerSec
            const y = (vp.maxMidi - m) * ROW_H + ROW_H / 2
            if (!open) { g.moveTo(x, y); open = true } else g.lineTo(x, y)
          })
          g.stroke({ width: 1.2, color: COLORS.f0, alpha: 0.75 })
          body.addChild(g)
        }

        const notes = new Graphics()
        const labels = new Container()
        for (const n of song.notes) {
          const x = n.start * vp.pxPerSec
          const w = Math.max(3, (n.end - n.start) * vp.pxPerSec)
          const y = (vp.maxMidi - n.midi) * ROW_H + 1
          const low = n.confidence < 0.5 || n.octave_suspect
          notes.roundRect(x, y, w, ROW_H - 2, 3).fill({ color: COLORS.note, alpha: 0.35 + 0.65 * n.confidence })
          if (n.id === selectedId) notes.roundRect(x, y, w, ROW_H - 2, 3).stroke({ width: 2, color: COLORS.sel })
          else if (low) notes.roundRect(x, y, w, ROW_H - 2, 3).stroke({ width: 1.5, color: COLORS.warn })
          if (view.labels && w >= 26) {
            const t = new BitmapText({ text: noteName(n.midi, song.key), style: { fontFamily: 'Arial', fontSize: 10, fill: 0x06121f } })
            t.x = x + 3
            t.y = y + 2
            labels.addChild(t)
          }
        }
        ghost = new Graphics()
        body.addChild(notes, labels, ghost)

        // แถบท่อน / คอร์ด / เนื้อร้อง (เลื่อนตามเวลา แต่ไม่เลื่อนตามแนวตั้ง)
        if (strips) { worldX.removeChild(strips); strips.destroy({ children: true }) }
        strips = new Container()
        strips.y = RULER_H
        const sg = new Graphics()
        sg.rect(0, 0, W, STRIP_H).fill(0x101319)
        const flats = preferFlats(song.key)
        const bt = (text: string, x: number, y: number, fill: number, size = 10) => {
          const t = new BitmapText({ text, style: { fontFamily: 'Arial', fontSize: size, fill } })
          t.x = x
          t.y = y
          strips!.addChild(t)
        }
        ;(song.sections ?? []).forEach((sec, i) => {
          const x0 = sec.start * vp.pxPerSec
          sg.rect(x0, 0, Math.max(1, (sec.end - sec.start) * vp.pxPerSec - 1), SEC_H - 1).fill({ color: i % 2 ? 0x2a3550 : 0x233049, alpha: sec.auto ? 0.8 : 1 })
        })
        strips.addChild(sg)
        ;(song.sections ?? []).forEach((sec) => bt(sec.label + (sec.auto ? '' : ' ✎'), sec.start * vp.pxPerSec + 4, 2, 0xb9c6e4, 10))
        ;(song.key_changes ?? []).forEach((k) => bt(`▶ ${k.tonic} ${k.mode}`, k.time * vp.pxPerSec, 2, 0xffa94d, 10))
        ;(song.chords ?? []).forEach((c) => {
          if (c.symbol === 'N') return
          bt(spellChord(c.symbol, flats), c.start * vp.pxPerSec + 2, SEC_H + 3, 0xffd666, 12)
        })
        if (view.labels) {
          for (const ln of song.lyrics?.lines ?? []) for (const w of ln.words) bt(w.text, w.start * vp.pxPerSec + 1, SEC_H + CH_H + 3, 0xcfd6e6, 11)
        }
        worldX.addChild(strips)
        drawFixed()
      }

      /** ส่วนที่ขึ้นกับ scroll: คีย์เปียโนด้านซ้ายและไม้บรรทัดเวลา (ถูกวาดใหม่เมื่อ scroll/zoom เปลี่ยน) */
      const drawFixed = () => {
        const { song } = stateRef.current
        keysBody.removeChildren().forEach((x) => x.destroy({ children: true }))
        ruler.removeChildren().forEach((x) => x.destroy({ children: true }))
        const W = a.screen.width
        const kg = new Graphics()
        kg.rect(0, 0, KEY_W, a.screen.height).fill(COLORS.ruler)
        for (let m = vp.minMidi; m <= vp.maxMidi; m++) {
          const y = rowY(m)
          if (y < TOP - ROW_H || y > a.screen.height) continue
          const pc = ((m % 12) + 12) % 12
          kg.rect(0, y, KEY_W - 1, ROW_H - 1).fill(BLACK.has(pc) ? COLORS.keyBlack : COLORS.key)
          if (pc === 0) {
            const t = new BitmapText({ text: noteName(m, song?.key), style: { fontFamily: 'Arial', fontSize: 10, fill: 0x20242e } })
            t.x = KEY_W - 28
            t.y = y + 2
            keysBody.addChild(t)
          }
        }
        keysBody.addChildAt(kg, 0)
        const rg = new Graphics()
        rg.rect(0, 0, W, RULER_H).fill(COLORS.ruler)
        const step = vp.pxPerSec >= 120 ? 1 : vp.pxPerSec >= 50 ? 5 : vp.pxPerSec >= 22 ? 10 : 30
        const t0 = Math.ceil(vp.scrollT / step) * step
        for (let t = t0; timeToX(t) < W; t += step) {
          const x = timeToX(t)
          if (x < KEY_W) continue
          rg.rect(x, RULER_H - 6, 1, 6).fill(COLORS.bar)
          const lab = new BitmapText({ text: `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`, style: { fontFamily: 'Arial', fontSize: 10, fill: COLORS.text } })
          lab.x = x + 3
          lab.y = 4
          ruler.addChild(lab)
        }
        ruler.addChildAt(rg, 0)
        rg.rect(0, 0, KEY_W, RULER_H).fill(COLORS.ruler)
      }

      const tr = getTransport()
      const tick = () => {
        const { view } = stateRef.current
        const t = tr.getTime()
        const viewW = a.screen.width - KEY_W
        if (view.follow && tr.playing) vp.scrollT = Math.max(0, t - (viewW * 0.3) / vp.pxPerSec)
        worldX.x = KEY_W - vp.scrollT * vp.pxPerSec
        body.y = TOP - vp.scrollY
        const sig = vp.scrollT * 1000 + vp.scrollY + view.pxPerSec * 1e6
        if (sig !== lastScale) { lastScale = sig; drawFixed() }
        const px = timeToX(t)
        playhead.clear()
        if (px >= KEY_W) {
          playhead.rect(px - 1, 0, 2, a.screen.height).fill(COLORS.playhead)
        }
      }
      a.ticker.add(tick)

      const clampScroll = () => {
        const dur = stateRef.current.song?.source.duration ?? 0
        vp.scrollT = Math.max(-2, Math.min(vp.scrollT, dur))
        const contentH = (vp.maxMidi - vp.minMidi + 1) * ROW_H + TOP
        vp.scrollY = Math.max(0, Math.min(vp.scrollY, Math.max(0, contentH - a.screen.height)))
      }

      const canvas = a.canvas
      const onWheel = (e: WheelEvent) => {
        e.preventDefault()
        const st = useStore.getState()
        if (e.ctrlKey) {
          const rect = canvas.getBoundingClientRect()
          const x = e.clientX - rect.left
          const tAt = vp.scrollT + (x - KEY_W) / vp.pxPerSec
          const next = Math.max(15, Math.min(600, st.view.pxPerSec * (e.deltaY < 0 ? 1.15 : 1 / 1.15)))
          vp.scrollT = tAt - (x - KEY_W) / next
          st.setView({ pxPerSec: next })
        } else if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY) || e.clientY - canvas.getBoundingClientRect().top < TOP) { // เลื่อนล้อบนไม้บรรทัด/แถบท่อนคอร์ด = เลื่อนเวลา
          vp.scrollT += (e.shiftKey || Math.abs(e.deltaX) <= Math.abs(e.deltaY) ? e.deltaY : e.deltaX) / vp.pxPerSec
          if (st.view.follow) st.setView({ follow: false })
        } else {
          vp.scrollY += e.deltaY
        }
        clampScroll()
      }
      const posOf = (e: { clientX: number; clientY: number }) => {
        const rect = canvas.getBoundingClientRect()
        const x = e.clientX - rect.left
        const y = e.clientY - rect.top
        return { x, y, t: vp.scrollT + (x - KEY_W) / vp.pxPerSec, midi: vp.maxMidi - Math.floor((y - TOP + vp.scrollY) / ROW_H) }
      }
      const drawGhost = () => {
        ghost.clear()
        if (!drag || !drag.moved) return
        const x = drag.start * vp.pxPerSec
        const w = Math.max(3, (drag.end - drag.start) * vp.pxPerSec)
        const y = (vp.maxMidi - drag.midi) * ROW_H + 1
        ghost.roundRect(x, y, w, ROW_H - 2, 3).fill({ color: COLORS.sel, alpha: 0.25 }).stroke({ width: 2, color: COLORS.sel })
      }
      const onDown = (e: PointerEvent) => {
        const { x, y, t, midi } = posOf(e)
        if (x < KEY_W) {
          // คลิกคีย์เปียโน = ฟังโน้ตนั้น
          if (y > TOP) tr.audition(vp.maxMidi - Math.floor((y - TOP + vp.scrollY) / ROW_H))
          return
        }
        const { song } = stateRef.current
        if (y > TOP && song) {
          const n = hitNote(song.notes, t, midi, 4 / vp.pxPerSec)
          if (n) {
            useStore.getState().selectNote(n.id)
            tr.audition(n.midi, Math.min(0.8, n.end - n.start))
            const px0 = (n.start - vp.scrollT) * vp.pxPerSec + KEY_W
            const px1 = (n.end - vp.scrollT) * vp.pxPerSec + KEY_W
            const edge = Math.min(EDGE_PX, (px1 - px0) / 3)
            const mode: DragMode = x <= px0 + edge ? 'left' : x >= px1 - edge ? 'right' : 'move'
            drag = { mode, id: n.id, note: n, x0: x, y0: y, moved: false, midi: n.midi, start: n.start, end: n.end }
            window.addEventListener('pointermove', onDragMove)
            window.addEventListener('pointerup', onDragEnd, { once: true })
            return
          }
          useStore.getState().selectNote(null)
        }
        tr.seek(Math.max(0, t))
      }
      const onDragMove = (e: PointerEvent) => {
        if (!drag) return
        const { x, y, t } = posOf(e)
        if (!drag.moved && Math.abs(x - drag.x0) + Math.abs(y - drag.y0) < 4) return
        drag.moved = true
        const song = stateRef.current.song
        const snap = stateRef.current.view.snap && song ? (v: number) => snapTime(song.beats, v) : (v: number) => v
        if (drag.mode === 'move') drag.midi = drag.note.midi - Math.round((y - drag.y0) / ROW_H)
        else if (drag.mode === 'left') drag.start = Math.min(snap(t), drag.note.end - 0.04)
        else drag.end = Math.max(snap(t), drag.note.start + 0.04)
        drawGhost()
      }
      const onDragEnd = () => {
        window.removeEventListener('pointermove', onDragMove)
        const d = drag
        drag = null
        ghost.clear()
        if (!d || !d.moved) return
        const key = stateRef.current.song?.key ?? null
        if (d.mode === 'move') {
          if (d.midi !== d.note.midi) {
            useStore.getState().editNotes((ns) => setPitch(ns, d.id, d.midi, key))
            tr.audition(d.midi, 0.4)
          }
        } else if (d.start !== d.note.start || d.end !== d.note.end) {
          useStore.getState().editNotes((ns) => setTimes(ns, d.id, d.start, d.end, key))
        }
      }
      const onDbl = (e: MouseEvent) => {
        const { x, y, t, midi } = posOf(e)
        const { song, view } = stateRef.current
        if (x < KEY_W || y <= TOP || !song || hitNote(song.notes, t, midi, 4 / vp.pxPerSec)) return
        const start = view.snap ? snapTime(song.beats, t) : t
        const dur = song.beats.length > 1 ? snapTime(song.beats, start + (song.beats[1].time - song.beats[0].time)) - start : 0.3
        const r = addNote(song.notes, start, midi, Math.max(0.1, dur), song.key)
        useStore.getState().editNotes(() => r.notes, r.id)
        tr.audition(midi, 0.3)
      }
      const onHover = (e: PointerEvent) => {
        if (drag) return
        const { x, y, t, midi } = posOf(e)
        const { song } = stateRef.current
        let cur = 'default'
        if (x >= KEY_W && y > TOP && song) {
          const n = hitNote(song.notes, t, midi, 4 / vp.pxPerSec)
          if (n) {
            const px0 = (n.start - vp.scrollT) * vp.pxPerSec + KEY_W
            const px1 = (n.end - vp.scrollT) * vp.pxPerSec + KEY_W
            const edge = Math.min(EDGE_PX, (px1 - px0) / 3)
            cur = x <= px0 + edge || x >= px1 - edge ? 'ew-resize' : 'ns-resize'
          }
        }
        canvas.style.cursor = cur
      }
      canvas.addEventListener('wheel', onWheel, { passive: false })
      canvas.addEventListener('pointerdown', onDown)
      canvas.addEventListener('dblclick', onDbl)
      canvas.addEventListener('pointermove', onHover)
      const ro = new ResizeObserver(() => { lastScale = 0; clampScroll() })
      ro.observe(el)

      api.current = {
        rebuild,
        scrollTo: (t: number) => { vp.scrollT = Math.max(-2, t - ((a.screen.width - KEY_W) * 0.3) / vp.pxPerSec) },
      }
      rebuild()
      cleanup = () => {
        canvas.removeEventListener('wheel', onWheel)
        canvas.removeEventListener('pointerdown', onDown)
        canvas.removeEventListener('dblclick', onDbl)
        canvas.removeEventListener('pointermove', onHover)
        window.removeEventListener('pointermove', onDragMove)
        ro.disconnect()
      }
    })()

    return () => {
      disposed = true
      cleanup()
      api.current = null
      if (app) { app.destroy(true, { children: true }); app = null }
    }
  }, [])

  useEffect(() => { if (focus) api.current?.scrollTo(focus.t) }, [focus])

  useEffect(() => { api.current?.rebuild() }, [song, f0, view.pxPerSec, view.showF0, view.labels, view.highlightKey, selectedId])

  return <div ref={host} className="pianoroll" data-testid="pianoroll" />
}
