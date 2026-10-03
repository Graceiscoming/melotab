// ทดสอบเส้นทางหลักผ่านหน้าเว็บ: อัปโหลดไฟล์ → งานวิเคราะห์ (status bar) → เปิด Piano Roll อัตโนมัติ
import puppeteer from 'puppeteer-core'
import fs from 'node:fs'
const OUT = process.env.SHOTS ?? '../../testdata/shots'
fs.mkdirSync(OUT, { recursive: true })
const file = process.env.FILE ?? 'D:/melotab/testdata/song01.mp4'
const browser = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new',
  args: ['--autoplay-policy=no-user-gesture-required', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'], defaultViewport: { width: 1400, height: 850 } })
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
await page.goto('http://localhost:5173', { waitUntil: 'networkidle0' })
await page.waitForSelector('[data-testid=statusbar] .dot.ok')
const input = await page.$('[data-testid=fileinput]')
const t0 = Date.now()
await input.uploadFile(file)
const seen = new Set()
await page.waitForFunction(() => document.querySelector('[data-testid=pianoroll] canvas'), { timeout: 600000, polling: 300 })
console.log('เปิด Piano Roll อัตโนมัติหลัง', ((Date.now() - t0) / 1000).toFixed(1), 's')
console.log('notes:', await page.$eval('[data-testid=notecount]', (e) => e.textContent))
await page.click('[data-testid=statusbar] .link').catch(() => {})
await new Promise((r) => setTimeout(r, 500))
console.log('jobpanel:', await page.$eval('[data-testid=jobpanel]', (e) => e.innerText.replace(/\n/g, ' | ')).catch(() => '(ไม่มี)'))
await page.screenshot({ path: `${OUT}/5-upload-done.png` })
console.log('errors:', errors.length ? errors : 'none')
await browser.close()
