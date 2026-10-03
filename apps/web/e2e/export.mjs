// ทดสอบเทคนิคอัตโนมัติ + Export บนหน้าเว็บจริง (ต้องรัน backend :8000 + vite :5173 และมีโปรเจกต์ song02 ที่วิเคราะห์แล้ว)
import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const OUT = process.env.SHOTS ?? '../../testdata/shots'
fs.mkdirSync(OUT, { recursive: true })
let failed = 0
const check = (name, cond, extra = '') => { console.log(cond ? 'PASS' : 'FAIL', name, extra); if (!cond) failed++ }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new',
  args: ['--autoplay-policy=no-user-gesture-required', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  defaultViewport: { width: 1500, height: 900 },
})
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
await page.goto('http://localhost:5173', { waitUntil: 'networkidle0' })
await page.waitForSelector('[data-testid=statusbar] .dot.ok')
const pid = await page.evaluate(async () => {
  const ps = await fetch('http://localhost:8000/projects').then((r) => r.json())
  return ps.filter((p) => p.analyzed && /song02/.test(p.title)).sort((a, b) => b.created - a.created)[0].id
})
await page.evaluate((id) => window.__melotab.getState().openProject(id), pid)
await page.waitForSelector('[data-testid=pianoroll] canvas')
await sleep(1000)
await page.click('[data-testid=mode-tab]')
await page.waitForFunction(() => window.__melotab.getState().tab?.events?.length > 0, { timeout: 30000 })
const G = () => page.evaluate(() => { const s = window.__melotab.getState(); return { n: s.song.notes.length, ev: s.tab.events.length, tech: s.techniques } })
let g = await G()
check('มีแทปครบทุกโน้ต', g.ev === g.n, `${g.ev}/${g.n}`)

// เทคนิคอัตโนมัติ
await page.click('[data-testid=auto-tech]')
await page.waitForFunction(() => document.querySelector('[data-testid=auto-tech-msg]')?.textContent.includes('ใส่เทคนิค'), { timeout: 30000 })
const msg = await page.$eval('[data-testid=auto-tech-msg]', (e) => e.textContent)
g = await G()
const kinds = { vib: 0, hp: 0, bend: 0, slide: 0 }
for (const t of Object.values(g.tech)) {
  if (t.on?.includes('vibrato')) kinds.vib++
  if (t.to_next === 'hammer' || t.to_next === 'pull') kinds.hp++
  if (t.on?.includes('bend')) kinds.bend++
  if (t.to_next === 'slide' || t.in === 'slide_in') kinds.slide++
}
check('ระบบใส่เทคนิคให้หลายโน้ต', Object.keys(g.tech).length > 20, `${Object.keys(g.tech).length} โน้ต ${JSON.stringify(kinds)} | ${msg}`)
const before = Object.keys(g.tech).length
check('vibrato ไม่อยู่บนสายเปล่า', await page.evaluate(() => {
  const s = window.__melotab.getState()
  return s.tab.events.every((e) => !(e.fret === 0 && s.techniques[e.note_id]?.on?.some((x) => x === 'vibrato' || x === 'bend')))
}))
// กดซ้ำไม่เพิ่ม (ไม่ทับ/ไม่ซ้ำ)
await page.click('[data-testid=auto-tech]')
await sleep(1500)
g = await G()
check('กดซ้ำไม่เปลี่ยนจำนวน', Object.keys(g.tech).length === before)
// undo ถอนเทคนิคทั้งหมดที่ใส่อัตโนมัติ
await page.evaluate(() => window.__melotab.getState().undo())
g = await G()
check('undo ถอนเทคนิคอัตโนมัติได้', Object.keys(g.tech).length === 0)
await page.click('[data-testid=auto-tech]')
await page.waitForFunction(() => Object.keys(window.__melotab.getState().techniques).length > 20, { timeout: 30000 })
await page.screenshot({ path: `${OUT}/20-tab-auto-techniques.png` })

// Export dialog
await page.click('[data-testid=export-btn]')
await page.waitForSelector('[data-testid=export-modal]')
for (const f of ['svg', 'pdf', 'midi', 'musicxml', 'gp5', 'txt', 'chordsheet', 'lrc']) await page.click(`[data-testid=fmt-${f}]`)
await page.select('[data-testid=export-preset]', 'ig_portrait')
await page.click('[data-testid=export-run]')
await page.waitForSelector('[data-testid=export-result]', { timeout: 120000 })
await sleep(300)
const files = await page.$$eval('[data-testid=export-file]', (as) => as.map((a) => ({ name: a.textContent, href: a.href })))
const exts = new Set(files.map((f) => f.name.split('.').pop()))
check('ได้ไฟล์ครบทุกฟอร์แมต', ['png', 'svg', 'pdf', 'mid', 'musicxml', 'gp5', 'txt'].every((e) => exts.has(e)), [...exts].join(','))
const sections = await page.evaluate(() => window.__melotab.getState().song.sections.length)
check('PNG แยกไฟล์ต่อท่อน', files.filter((f) => f.name.endsWith('.png')).length >= sections, `${files.filter((f) => f.name.endsWith('.png')).length} ไฟล์ / ${sections} ท่อน`)
const sizes = await page.evaluate(async (fs_) => Promise.all(fs_.map(async (f) => [f.name, (await (await fetch(f.href)).arrayBuffer()).byteLength])), files)
check('ทุกไฟล์ดาวน์โหลดได้และไม่ว่าง', sizes.every(([, n]) => n > 100), JSON.stringify(sizes.filter(([, n]) => n <= 100)))
// ภาพตัวอย่าง
const png = files.find((f) => f.name.endsWith('.png'))
fs.writeFileSync(`${OUT}/21-export-sample.png`, Buffer.from(await (await fetch(png.href)).arrayBuffer()))
await page.screenshot({ path: `${OUT}/22-export-dialog.png` })
check('ไม่มี console error', errors.length === 0, errors.join(' | '))
await browser.close()
process.exit(failed ? 1 : 0)
