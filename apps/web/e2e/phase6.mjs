// ทดสอบ Phase 6 บนหน้าเว็บจริง: Model Manager, Batch (UI), ไลน์ประสาน, โหมดซ้อม (คอกีตาร์วิ่ง + ไมค์ปลอม 440 Hz), Export วิดีโอ
// ต้องรัน backend :8000 + vite :5173 และมีโปรเจกต์ song01 ที่วิเคราะห์แล้ว
import puppeteer from 'puppeteer-core'
import fs from 'node:fs'
import path from 'node:path'

const OUT = process.env.SHOTS ?? '../../testdata/shots'
fs.mkdirSync(OUT, { recursive: true })
const MIC = path.resolve('../../testdata/mic440.wav')
let failed = 0
const check = (name, cond, extra = '') => { console.log(cond ? 'PASS' : 'FAIL', name, extra); if (!cond) failed++ }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new',
  args: ['--autoplay-policy=no-user-gesture-required', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-audio-capture=${MIC}`],
  defaultViewport: { width: 1500, height: 900 },
})
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('response', (r) => { if (r.status() === 404) console.log('404:', r.url()) })
page.on('dialog', (d) => d.dismiss())
await page.goto('http://localhost:5173', { waitUntil: 'networkidle0' })
await page.waitForSelector('[data-testid=statusbar] .dot.ok')

// ---- Library: Model Manager + Batch panel
await page.click('[data-testid=models] summary')
await page.waitForSelector('[data-testid=model-row]')
const rows = await page.$$eval('[data-testid=model-row]', (r) => r.map((x) => x.textContent))
check('Model Manager แสดงโมเดลครบและสถานะพร้อม', rows.length >= 7 && rows.filter((r) => r.includes('✓ พร้อม')).length >= 6, `${rows.length} แถว`)
const delBtns = await page.$$eval('[data-testid=model-row] button', (b) => b.length)
check('ปุ่มลบมีเฉพาะโมเดลที่โหลดอัตโนมัติ (ไม่ใช่ SOME/RMVPE/BTC)', delBtns === 4, `${delBtns} ปุ่ม`) // separation, karaoke, dereverb, whisper
await page.click('[data-testid=batch] summary')
await page.type('[data-testid=batch-text]', 'D:\ไม่มีโฟลเดอร์นี้')
await page.click('[data-testid=batch-run]')
await page.waitForSelector('[data-testid=batch-msg]')
check('Batch โฟลเดอร์ที่ไม่มี แสดงข้อผิดพลาด ไม่ล้ม', (await page.$eval('[data-testid=batch-msg]', (e) => e.textContent)).includes('ไม่พบโฟลเดอร์'))

// ---- เปิดโปรเจกต์
const pid = await page.evaluate(async () => {
  const ps = await fetch('http://localhost:8000/projects').then((r) => r.json())
  return ps.filter((p) => p.analyzed && /song01/.test(p.title)).sort((a, b) => b.created - a.created)[0].id
})
await page.evaluate((id) => window.__melotab.getState().openProject(id), pid)
await page.waitForSelector('[data-testid=pianoroll] canvas')
await sleep(800)
await page.click('[data-testid=mode-tab]')
await page.waitForFunction(() => window.__melotab.getState().tab?.events?.length > 0, { timeout: 30000 })

// ---- ไลน์ประสาน
await page.click('[data-testid=harmony-btn]')
await page.waitForSelector('[data-testid=harmony-text]')
const ht = await page.$eval('[data-testid=harmony-text]', (e) => e.textContent)
check('ไลน์ประสานแสดงแทป 6 สาย', ht.includes('e|') && ht.includes('E|') && /\d/.test(ht), `${ht.length} ตัวอักษร`)
await page.screenshot({ path: `${OUT}/30-harmony.png` })
await page.click('[data-testid=harmony-modal] .row button:last-child')

// ---- โหมดซ้อม
await page.click('[data-testid=mode-practice]')
await page.waitForSelector('[data-testid=bigfret]')
const ids = new Set()
await page.evaluate(() => window.__getTransport().seek(2))
await page.click('[data-testid=play]')
for (let i = 0; i < 20; i++) {
  const id = await page.$eval('[data-testid=bigfret-cur]', (e) => e.getAttribute('data-id')).catch(() => null)
  if (id) ids.add(id)
  await sleep(150)
}
check('คอกีตาร์วิ่งตามเพลง (โน้ตปัจจุบันเปลี่ยนเรื่อย ๆ)', ids.size >= 3, `${ids.size} โน้ตใน 3 วินาที`)
await page.click('[data-testid=mic-start]')
await page.waitForSelector('[data-testid=mic-stop]', { timeout: 10000 })
await sleep(1500)
const heard = await page.$eval('[data-testid=pr-heard]', (e) => e.textContent)
check('ไมค์ปลอม 440 Hz ถูกตรวจเป็น A4 (±ไม่กี่ cents)', /^A4 \(([+-]?\d+)¢\)/.test(heard) && Math.abs(parseInt(heard.match(/\(([+-]?\d+)¢/)[1])) <= 10, heard)
const sc = await page.$eval('[data-testid=pr-score]', (e) => e.textContent)
check('มีคะแนนแสดง', /%$/.test(sc), sc)
await page.screenshot({ path: `${OUT}/31-practice.png` })
await page.click('[data-testid=play]')
await page.click('[data-testid=mic-stop]')
check('ปิดไมค์ได้', !!(await page.$('[data-testid=mic-start]')))

// ---- Export วิดีโอ (song01 ไม่มีท่อน → ทั้งเพลงเป็นวิดีโอเดียว)
await page.click('[data-testid=export-btn]')
await page.waitForSelector('[data-testid=export-modal]')
await page.click('[data-testid=fmt-png]') // ปิด png
await page.click('[data-testid=fmt-video]')
await page.click('[data-testid=fmt-harmony]')
await page.click('[data-testid=export-run]')
await page.waitForSelector('[data-testid=export-result], [data-testid=export-error]', { timeout: 280000 })
const err = await page.$('[data-testid=export-error]')
check('Export วิดีโอ+ไลน์ประสานสำเร็จ', !err, err ? await err.evaluate((e) => e.textContent) : '')
const files = await page.$$eval('[data-testid=export-file]', (as) => as.map((a) => a.textContent))
check('ได้ไฟล์ mp4 + harmony mid/txt', files.some((f) => f.endsWith('.mp4')) && files.some((f) => f.endsWith('_harmony.mid')) && files.some((f) => f.endsWith('_harmony_tab.txt')), files.join(', '))
const real = errors.filter((e) => !e.includes('404 (Not Found)')) // 404 จากการทดสอบโฟลเดอร์ที่ไม่มีใน Batch (ตั้งใจ)
check('ไม่มี console error', real.length === 0, real.join(' | '))
await browser.close()
process.exit(failed ? 1 : 0)
