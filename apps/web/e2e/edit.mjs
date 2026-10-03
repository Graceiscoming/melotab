// ทดสอบการแก้โน้ตด้วยเมาส์/คีย์บอร์ดบนหน้าเว็บจริง + autosave + undo/redo  (ต้องรัน backend :8000 + vite :5173)
import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const OUT = process.env.SHOTS ?? '../../testdata/shots'
fs.mkdirSync(OUT, { recursive: true })
let failed = 0
const check = (name, cond, extra = '') => {
  console.log(cond ? 'PASS' : 'FAIL', name, extra)
  if (!cond) failed++
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: 'new',
  args: ['--autoplay-policy=no-user-gesture-required', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  defaultViewport: { width: 1400, height: 850 },
})
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('dialog', (d) => d.accept())
await page.goto('http://localhost:5173', { waitUntil: 'networkidle0' })
await page.waitForSelector('[data-testid=statusbar] .dot.ok')

const pid = await page.evaluate(async () => {
  const ps = await fetch('http://localhost:8000/projects').then((r) => r.json())
  return ps.filter((p) => p.analyzed && /song01/.test(p.title)).sort((a, b) => b.created - a.created)[0].id
})
await page.evaluate((id) => window.__melotab.getState().openProject(id), pid)
await page.waitForSelector('[data-testid=pianoroll] canvas')
await page.waitForFunction(() => !document.querySelector('[data-testid=play]').disabled, { timeout: 30000 })
await sleep(700)

const S = () => page.evaluate(() => {
  const s = window.__melotab.getState()
  return { notes: s.song.notes, sel: s.selectedNoteId, save: s.saveState, past: s.past.length }
})
const geo = () => page.evaluate(() => {
  const s = window.__melotab.getState()
  const ms = s.song.notes.map((n) => n.midi)
  const r = document.querySelector('[data-testid=pianoroll] canvas').getBoundingClientRect()
  return { left: r.left, top: r.top, maxMidi: Math.max(...ms) + 3, px: s.view.pxPerSec }
})
const xy = async (t, midi) => {
  const g = await geo()
  return [g.left + 64 + t * g.px, g.top + 22 + (g.maxMidi - midi) * 16 + 8]
}

const before = await S()
const target = before.notes.find((n) => n.end - n.start > 0.4 && n.start > 1.5)

// 1) ลากโน้ตขึ้น 2 แถว → pitch +2
let [x, y] = await xy((target.start + target.end) / 2, target.midi)
await page.mouse.move(x, y)
await page.mouse.down()
await page.mouse.move(x, y - 16, { steps: 4 })
await page.mouse.move(x, y - 32, { steps: 4 })
await page.screenshot({ path: `${OUT}/6-dragging.png` })
await page.mouse.up()
await sleep(200)
const s1 = await S()
const n1 = s1.notes.find((n) => n.id === target.id)
check('ลากขึ้น 2 แถว → midi +2', n1.midi === target.midi + 2, `${target.midi}→${n1.midi}`)
check('โน้ตที่แก้ถูกติดธง edited และ confidence = 1', n1.edited === true && n1.confidence === 1)
check('จำนวนโน้ตไม่เปลี่ยน', s1.notes.length === before.notes.length)
check('สถานะ dirty/saving (autosave กำลังจะทำงาน)', s1.save === 'dirty' || s1.save === 'saving')

// 2) autosave ถึง backend
await page.waitForFunction(() => window.__melotab.getState().saveState === 'saved', { timeout: 8000 })
const saved = await page.evaluate(
  async (id, nid) => (await fetch(`http://localhost:8000/projects/${id}`).then((r) => r.json())).song.notes.find((n) => n.id === nid).midi,
  pid, target.id)
check('autosave เขียนลง backend แล้ว', saved === target.midi + 2, `backend midi=${saved}`)

// 3) undo / redo
await page.keyboard.down('Control'); await page.keyboard.press('KeyZ'); await page.keyboard.up('Control')
check('Ctrl+Z คืน pitch เดิม', (await S()).notes.find((n) => n.id === target.id).midi === target.midi)
await page.keyboard.down('Control'); await page.keyboard.press('KeyY'); await page.keyboard.up('Control')
check('Ctrl+Y ทำซ้ำ', (await S()).notes.find((n) => n.id === target.id).midi === target.midi + 2)

// 4) ลากขอบขวา → ความยาวเปลี่ยน
const cur = (await S()).notes.find((n) => n.id === target.id)
;[x, y] = await xy(cur.end - 0.01, cur.midi)
await page.mouse.move(x, y)
await page.mouse.down()
await page.mouse.move(x + 30, y, { steps: 5 })
await page.mouse.up()
await sleep(200)
const n2 = (await S()).notes.find((n) => n.id === target.id)
check('ลากขอบขวา → โน้ตยาวขึ้น', n2.end > cur.end + 0.1, `${cur.end.toFixed(2)}→${n2.end.toFixed(2)}`)

// 5) แบ่ง (S) + รวม (M)
const mid = (n2.start + n2.end) / 2
const countBefore = (await S()).notes.length
await page.evaluate((id) => window.__melotab.getState().selectNote(id), target.id)
await page.evaluate((t) => window.__getTransport().seek(t), mid)
await page.keyboard.press('KeyS')
await sleep(200)
{ const s = await S(); check('S แบ่งโน้ตเป็นสอง', s.notes.length === countBefore + 1, `count ${countBefore}→${s.notes.length} sel=${s.sel} target=${target.id} mode=${await page.evaluate(() => window.__melotab.getState().view.mode)} active=${await page.evaluate(() => document.activeElement?.tagName)}`) }
await page.keyboard.press('KeyM')
await sleep(200)
check('M รวมกลับ', (await S()).notes.length === countBefore)

// 6) ↑ + Delete
await page.keyboard.press('ArrowUp')
check('ลูกศรขึ้น +1 semitone', (await S()).notes.find((n) => n.id === target.id).midi === target.midi + 3)
await page.keyboard.press('Delete')
const afterDel = await S()
check('Delete ลบโน้ต', !afterDel.notes.some((n) => n.id === target.id) && afterDel.notes.length === countBefore - 1)

// 7) ดับเบิลคลิกที่ว่าง → เพิ่มโน้ต (เลือกช่องว่างระหว่างโน้ตที่ห่างกัน > 0.5 วินาที ให้แน่ใจว่าไม่ชนโน้ตข้างเคียง)
const ns = afterDel.notes
// ต้องอยู่ในช่วงที่มองเห็นบนจอ (เริ่ม scrollT = 0 กว้าง ~1300 px ที่ 90 px/s ≈ 14 วินาทีแรก)
const gi = ns.findIndex((n, i) => i < ns.length - 1 && n.end < 12 && ns[i + 1].start - n.end > 0.25)
if (gi < 0) throw new Error('ไม่พบช่องว่างในช่วงที่มองเห็นเพื่อทดสอบ')
const gapT = ns[gi].end + (ns[gi + 1].start - ns[gi].end) / 2
;[x, y] = await xy(gapT, ns[gi].midi)
// puppeteer mouse.click({clickCount:2}) ไม่ยิง dblclick → ส่งลำดับเมาส์ผ่าน CDP แบบเดียวกับที่เบราว์เซอร์จริงทำ
const cdp = await page.createCDPSession()
for (const cc of [1, 2]) {
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: cc })
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: cc })
}
await sleep(300)
const afterAdd = await S()
check('ดับเบิลคลิกเพิ่มโน้ตใหม่', afterAdd.notes.length === afterDel.notes.length + 1, `count ${afterAdd.notes.length}`)

// 8) ปุ่ม N ข้ามไปโน้ตที่ควรตรวจ
await page.keyboard.press('KeyN')
await sleep(300)
const st = await S()
const reviewNote = st.notes.find((n) => n.id === st.sel)
check('N เลือกโน้ตที่ควรตรวจ', !!reviewNote && (reviewNote.confidence < 0.5 || reviewNote.octave_suspect), reviewNote ? `conf=${reviewNote.confidence}` : '')
await page.screenshot({ path: `${OUT}/7-edited.png` })

// เก็บกวาด: ย้อนทุกอย่างกลับ + บันทึก ไม่ทิ้งการแก้ทดสอบไว้ในโปรเจกต์
await page.evaluate(async () => {
  while (window.__melotab.getState().past.length) window.__melotab.getState().undo()
  await window.__melotab.getState().saveNow()
})
const final = await S()
check('ย้อนกลับทั้งหมดได้ครบ',
  final.notes.length === before.notes.length && JSON.stringify(final.notes.map((n) => n.midi)) === JSON.stringify(before.notes.map((n) => n.midi)))
console.log('errors:', errors.length ? errors : 'none')
await browser.close()
process.exit(failed ? 1 : 0)
