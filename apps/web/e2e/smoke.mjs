// ทดสอบ UI จริงด้วย Chrome ที่ติดตั้งในเครื่อง: เปิดหน้า → เปิดโปรเจกต์ → เล่น → ถ่ายภาพ  (ต้องรัน backend :8000 + vite :5173 ก่อน)
import puppeteer from 'puppeteer-core'
const OUT = process.env.SHOTS ?? '../../testdata/shots'
import fs from 'node:fs'
fs.mkdirSync(OUT, { recursive: true })
const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new',
  args: ['--autoplay-policy=no-user-gesture-required', '--window-size=1400,850', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  defaultViewport: { width: 1400, height: 850 },
})
const page = await browser.newPage()
const errors = []
page.on('response', (r) => { if (r.status() >= 400) console.log('HTTP', r.status(), r.url()) })
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()) })
await page.goto('http://localhost:5173', { waitUntil: 'networkidle0' })
await page.waitForSelector('[data-testid=statusbar] .dot.ok', { timeout: 15000 })
await page.screenshot({ path: `${OUT}/1-library.png` })
const projects = await page.$$eval('.proj', (els) => els.map((e) => e.textContent))
console.log('projects:', projects)
const idx = Number(process.env.PROJ ?? 1)
await (await page.$$('.proj'))[idx].click()
await page.waitForSelector('[data-testid=pianoroll] canvas', { timeout: 20000 })
await page.waitForFunction(() => !document.querySelector('[data-testid=play]').disabled, { timeout: 30000 })
await new Promise((r) => setTimeout(r, 800))
console.log('key:', await page.$eval('[data-testid=key]', (e) => e.textContent), '| bpm:', await page.$eval('[data-testid=bpm]', (e) => e.textContent), '| notes:', await page.$eval('[data-testid=notecount]', (e) => e.textContent))
await page.screenshot({ path: `${OUT}/2-workspace.png` })
await page.click('[data-testid=play]')
await new Promise((r) => setTimeout(r, 2500))
const t = await page.$eval('[data-testid=time]', (e) => e.textContent)
console.log('time after play:', t)
await page.screenshot({ path: `${OUT}/3-playing.png` })
// คลิกโน้ตบน piano roll
await page.mouse.click(500, 400)
await new Promise((r) => setTimeout(r, 300))
console.log('notepanel:', await page.$eval('[data-testid=notepanel]', (e) => e.textContent).catch(() => '(ไม่มีโน้ตตรงจุดคลิก)'))
await page.screenshot({ path: `${OUT}/4-click.png` })
console.log('errors:', errors.length ? errors : 'none')
await browser.close()
