// ทดสอบหน้า Guitar Tab บนหน้าเว็บจริง: สร้างแทป ความถูกต้องของ pitch แก้ไข ล็อก เทคนิค ทางเลือก Block Mode แนะนำคีย์ undo
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
const TUN = { standard: [40, 45, 50, 55, 59, 64] }

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new',
  args: ['--autoplay-policy=no-user-gesture-required', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  defaultViewport: { width: 1500, height: 900 },
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
await sleep(800)

const G = () => page.evaluate(() => {
  const s = window.__melotab.getState()
  return { notes: s.song.notes, events: s.tab ? s.tab.events : null, summary: s.tab ? s.tab.summary : null, settings: s.tabSettings, locked: s.locked,
    techniques: s.techniques, sel: s.selectedNoteId, busy: s.tabBusy }
})
// รอผลแทปใหม่จาก engine จริง (tabVersion เพิ่ม) — ใช้หลังการกระทำที่ทำให้สร้างใหม่ (มี debounce ~450 ms)
let lastVersion = 0
const waitTab = async (ms = 10000) => {
  await page.waitForFunction((v) => { const s = window.__melotab.getState(); return s.tabVersion > v && !s.tabBusy }, { timeout: ms }, lastVersion)
  lastVersion = await page.evaluate(() => window.__melotab.getState().tabVersion)
}
const press = async (code, mods = []) => {
  for (const m of mods) await page.keyboard.down(m)
  await page.keyboard.press(code)
  for (const m of mods) await page.keyboard.up(m)
}
const pitchOk = (g) => g.events.every((e) => e.fret === null || TUN.standard[6 - e.string] + g.settings.capo + e.fret === e.pitch)

// 1) เข้าโหมดแทป → สร้างให้อัตโนมัติ
await page.click('[data-testid=mode-tab]')
await page.waitForSelector('[data-testid=tab-event]', { timeout: 15000 })
// สั่งสร้างเองเพื่อไม่ขึ้นกับ tab.json ที่ค้างจากรอบก่อน (ถ้ามี แทปจะถูกโหลดจากไฟล์ ไม่สร้างใหม่)
await page.evaluate(() => window.__melotab.getState().setTabSettings({ transpose: 0, capo: 0, blocks: [] }))
await waitTab()
let g = await G()
check('สร้างแทปให้ทุกโน้ต', g.events.length === g.notes.length, `${g.events.length}/${g.notes.length}`)
check('ทุกตำแหน่งให้ pitch ที่ถูกต้องตามจูนนิ่ง', pitchOk(g))
check('pitch ของ event = pitch ของโน้ต + transpose', g.events.every((e) => { const n = g.notes.find((x) => x.id === e.note_id); return e.pitch === n.midi + g.settings.transpose }))
const rendered = await page.$$eval('[data-testid=tab-event]', (els) => els.length)
check('วาดเลขบนแทปครบทุก event ที่เล่นได้', rendered === g.events.filter((e) => e.fret !== null).length, `${rendered}`)
check('แสดงคะแนนความยาก', (await page.$eval('[data-testid=difficulty]', (e) => Number(e.textContent))) >= 1)
await page.screenshot({ path: `${OUT}/8-tab.png` })

// 2) เลือก event แล้วย้ายสาย (↓ = สายหนาขึ้น) รักษา pitch
const first = g.events.find((e) => e.fret !== null && e.string <= 4)
await page.evaluate((id) => window.__melotab.getState().selectNote(id), first.note_id)
await sleep(150)
await press('ArrowDown')
await waitTab()
g = await G()
let e1 = g.events.find((e) => e.note_id === first.note_id)
check('↓ ย้ายลงสายหนา 1 สาย', e1.string === first.string + 1, `สาย ${first.string}→${e1.string}`)
check('ย้ายสายแล้ว pitch เดิม', e1.pitch === first.pitch && g.notes.find((n) => n.id === first.note_id).midi === g.notes.find((n) => n.id === first.note_id).midi)
check('ตำแหน่งที่แก้ถูกล็อกอัตโนมัติ', !!g.locked[first.note_id] && e1.locked === true)
check('ทุกตำแหน่งยังถูกต้องหลังสร้างใหม่', pitchOk(g))

// 3) พิมพ์เลขช่อง → pitch ของโน้ตเปลี่ยนตาม
const midiBefore = g.notes.find((n) => n.id === first.note_id).midi
const targetFret = e1.fret >= 5 ? e1.fret - 1 : e1.fret + 1
const digits = String(targetFret).split('')
for (const d of digits) await press(`Digit${d}`)
await waitTab()
g = await G()
const noteAfter = g.notes.find((n) => n.id === first.note_id)
e1 = g.events.find((e) => e.note_id === first.note_id)
check('พิมพ์เลขช่อง → โน้ตเปลี่ยน pitch ±1', Math.abs(noteAfter.midi - midiBefore) === 1 && noteAfter.edited, `${midiBefore}→${noteAfter.midi}`)
check('ช่องบนแทปตรงที่พิมพ์', e1.fret === targetFret, `fret=${e1.fret}`)

// 4) เทคนิค H → สัญลักษณ์ h ที่โน้ตนั้น
await press('KeyH')
await sleep(200)
g = await G()
check('H ใส่ hammer-on (to_next)', g.techniques[first.note_id]?.to_next === 'hammer')
const hasMark = await page.$$eval('[data-ev] text', (ts) => ts.some((t) => t.textContent === 'h'))
check('แสดงสัญลักษณ์ h บนแทป', hasMark)
await press('KeyH')
await sleep(150)
check('กด H ซ้ำ = ถอด', (await G()).techniques[first.note_id] === undefined)

// 5) ตำแหน่งทางเลือก
await page.click('[data-testid=alts-btn]')
await page.waitForSelector('[data-testid=alts-list] li', { timeout: 10000 })
const nAlts = await page.$$eval('[data-testid=alts-list] li', (l) => l.length)
check('มีตำแหน่งทางเลือก', nAlts >= 1, `${nAlts}`)
const altText = await page.$eval('[data-testid=alts-list] li button', (b) => b.textContent)
await page.click('[data-testid=alts-list] li button')
await waitTab()
g = await G()
e1 = g.events.find((e) => e.note_id === first.note_id)
const m = altText.match(/สาย (\d) ช่อง (\d+)/)
check('เลือกทางเลือก → ล็อกที่ตำแหน่งนั้น', e1.string === Number(m[1]) && e1.fret === Number(m[2]), altText)
check('pitch ถูกต้องหลังเลือกทางเลือก', pitchOk(g))

// 6) Capo 2 → ช่องลดลง pitch ยังถูก
const fretsBefore = g.events.filter((e) => e.fret !== null && !g.locked[e.note_id]).map((e) => e.fret)
await page.$eval('[data-testid=capo]', (el) => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(el, '2'); el.dispatchEvent(new Event('input', { bubbles: true })) })
await sleep(500)
await waitTab()
g = await G()
check('ตั้ง capo 2 แล้ว pitch ถูกต้องทุกตัว', g.settings.capo === 2 && pitchOk(g))
check('capo ยังรักษาโน้ตทั้งหมด (ไม่มีโน้ตหาย)', g.summary.unplayable === 0 && g.events.length === g.notes.length)
await page.screenshot({ path: `${OUT}/9-tab-capo.png` })

// 7) Block Mode
await page.select('[data-testid=block-system]', 'position')
await page.waitForSelector('[data-testid=block-chip]', { timeout: 10000 })
const chips = await page.$$('[data-testid=block-chip]')
check('มี block ให้เลือกหลายอัน', chips.length >= 5, `${chips.length}`)
await chips[Math.floor(chips.length / 2)].click()
await sleep(400)
await waitTab()
g = await G()
const blk = g.settings.blocks[0]
check('เลือก block แล้วเก็บใน settings', g.settings.blocks.length === 1)
const inside = g.events.filter((e) => e.fret !== null && !g.locked[e.note_id] && !e.warnings.includes('out_of_block') && !e.warnings.includes('octave_shifted'))
check('โน้ตที่ไม่ได้ล็อก/ไม่มีธง อยู่ในช่วงช่องของ block ทั้งหมด', inside.every((e) => e.fret >= blk.fret_min && e.fret <= blk.fret_max), `block ${blk.fret_min}-${blk.fret_max}`)
check('pitch ถูกต้องหลังใช้ block', pitchOk(g))
const cov = await page.$eval('[data-testid=coverage]', (e) => e.textContent).catch(() => '')
check('แสดง % โน้ตที่อยู่ใน block', /%/.test(cov), cov)
await page.screenshot({ path: `${OUT}/10-tab-block.png` })
await page.select('[data-testid=block-system]', 'none')
await sleep(400)
await waitTab()
check('ปิด Block Mode แล้วไม่มี block ใน settings', (await G()).settings.blocks.length === 0)

// 8) แนะนำคีย์ + Capo
await page.click('[data-testid=suggest-btn]')
await page.waitForSelector('[data-testid=suggest-table] tbody tr', { timeout: 20000 })
const tables = await page.$$eval('[data-testid=suggest-table]', (ts) => ts.map((t) => t.querySelectorAll('tbody tr').length))
check('ตารางแนะนำคีย์ 2 กลุ่ม', tables.length === 2 && tables.every((n) => n > 0), JSON.stringify(tables))
await page.screenshot({ path: `${OUT}/11-keysuggest.png` })
const optText = await page.$eval('[data-testid=suggest-table] tbody tr:nth-child(2)', (r) => r.innerText.replace(/\s+/g, ' '))
await page.evaluate(() => document.querySelectorAll('[data-testid=use-option]')[1].click())
await sleep(500)
await waitTab()
g = await G()
check('กด "ใช้" แล้ว settings เปลี่ยนตามตัวเลือก', g.settings.transpose !== 0 || g.settings.capo !== 2, `transpose=${g.settings.transpose} capo=${g.settings.capo} (${optText})`)
check('pitch ถูกต้องหลังใช้ตัวเลือกคีย์', pitchOk(g) && g.events.every((e) => e.fret === null || e.pitch === g.notes.find((n) => n.id === e.note_id).midi + g.settings.transpose || e.warnings.includes('octave_shifted')))

// 9) undo (Ctrl+Z) ย้อนการแก้โน้ต/ล็อก
await page.evaluate(() => window.__melotab.getState().setTabSettings({ transpose: 0, capo: 0 }))
await waitTab()
let undone = 0
while ((await G()).notes.some((n) => n.edited) || Object.keys((await G()).locked).length) {
  await press('KeyZ', ['Control']); undone++
  if (undone > 20) break
}
await waitTab()
g = await G()
check('Ctrl+Z ย้อนการแก้ทั้งหมด (โน้ต + ล็อก)', !g.notes.some((n) => n.edited) && Object.keys(g.locked).length === 0, `undo ${undone} ครั้ง`)
await page.evaluate(async () => { await window.__melotab.getState().saveNow() })
check('autosave แทปลง backend', await page.evaluate(async (id) => { const t = await fetch(`http://localhost:8000/projects/${id}/tab`).then((r) => r.json()); return Array.isArray(t.events) && t.events.length > 0 }, pid))
console.log('errors:', errors.length ? errors : 'none')
await browser.close()
process.exit(failed ? 1 : 0)
