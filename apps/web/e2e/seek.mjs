// ทดสอบการกลับไปต้นเพลง: ปุ่ม ⏮, แถบเลื่อนเวลา, คีย์ Home, ล้อเมาส์บนไม้บรรทัด (ต้องรัน backend :8000 + vite :5173)
import puppeteer from 'puppeteer-core'
let failed = 0
const check = (n, c, x = '') => { console.log(c ? 'PASS' : 'FAIL', n, x); if (!c) failed++ }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const browser = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new',
  args: ['--autoplay-policy=no-user-gesture-required', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'], defaultViewport: { width: 1500, height: 900 } })
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
await page.goto('http://localhost:5173', { waitUntil: 'networkidle0' })
await page.waitForSelector('[data-testid=statusbar] .dot.ok')
const pid = await page.evaluate(async () => (await fetch('http://localhost:8000/projects').then((r) => r.json())).filter((p) => p.analyzed && /song02/.test(p.title))[0].id)
await page.evaluate((id) => window.__melotab.getState().openProject(id), pid)
await page.waitForSelector('[data-testid=pianoroll] canvas')
await sleep(1500)
const T = () => page.evaluate(() => window.__getTransport().getTime())
const scrollInfo = () => page.evaluate(() => window.__melotab.getState().view.follow)

// ไปกลางเพลงก่อน
await page.$eval('[data-testid=seekbar]', (el) => { el.value = '150'; el.dispatchEvent(new Event('input', { bubbles: true })) })
await sleep(300)
check('แถบเลื่อนเวลาไปที่ ~150 s ได้', Math.abs((await T()) - 150) < 1, `${(await T()).toFixed(1)}`)
await page.screenshot({ path: '../../testdata/shots/40-seek-mid.png' })
// ปิด follow (เหมือนผู้ใช้เลื่อนเอง) แล้วกด ⏮
await page.evaluate(() => window.__melotab.getState().setView({ follow: false }))
await page.click('[data-testid=to-start]')
await sleep(400)
check('⏮ กลับไปต้นเพลง', (await T()) < 0.1, `${(await T()).toFixed(2)}`)
check('⏮ เปิด "ตามเพลง" กลับ', await scrollInfo())
await page.screenshot({ path: '../../testdata/shots/41-seek-start.png' })
// Home
await page.$eval('[data-testid=seekbar]', (el) => { el.value = '100'; el.dispatchEvent(new Event('input', { bubbles: true })) })
await page.$eval('body', (b) => b.focus())
await page.evaluate(() => document.activeElement.blur())
await page.keyboard.press('Home')
await sleep(300)
check('คีย์ Home กลับต้นเพลง', (await T()) < 0.1)
// ล้อบนไม้บรรทัดเลื่อนเวลาไปข้างหลังได้
await page.$eval('[data-testid=seekbar]', (el) => { el.value = '60'; el.dispatchEvent(new Event('input', { bubbles: true })) })
await sleep(300)
const box = await (await page.$('[data-testid=pianoroll] canvas')).boundingBox()
await page.mouse.move(box.x + 400, box.y + 10)
for (let i = 0; i < 12; i++) { await page.mouse.wheel({ deltaY: -400 }); await sleep(30) }
await sleep(200)
await page.screenshot({ path: '../../testdata/shots/42-wheel-back.png' })
check('ไม่มี error', errors.length === 0, errors.join('|'))
await browser.close()
process.exit(failed ? 1 : 0)
