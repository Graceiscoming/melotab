// ทดสอบเครื่องมือซ้อม: slow-down (SoundTouch), count-in, loop A–B บนหน้าเว็บจริง (ต้องรัน backend :8000 + vite :5173)
import puppeteer from 'puppeteer-core'

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
  return ps.filter((p) => p.analyzed).sort((a, b) => a.created - b.created)[0].id // song ที่สั้นสุดพอ
})
await page.evaluate((id) => window.__melotab.getState().openProject(id), pid)
await page.waitForSelector('[data-testid=pianoroll] canvas')
await sleep(1500)
const T = () => page.evaluate(async () => { return window.__getTransport() })
const tm = () => page.evaluate(async () => window.__getTransport().getTime())

// slow-down
await page.select('[data-testid=rate]', '0.5')
await page.waitForFunction(() => !document.querySelector('[data-testid=rate]').disabled, { timeout: 120000 })
const info = await page.evaluate(async () => { const t = window.__getTransport(); return { rate: t.rate, dur: t.duration, st: [...t.stretched.values()].map((b) => b.duration) } })
check('ตั้งความเร็ว 50% แล้ว buffer ยาวขึ้น ~2 เท่า', info.rate === 0.5 && info.st.length === 1 && Math.abs(info.st[0] / info.dur - 2) < 0.05, JSON.stringify(info))
await page.click('[data-testid=play]')
await sleep(2000)
const t1 = await tm()
check('เล่นที่ 50%: เวลาเพลงเดินช้าลงครึ่งหนึ่ง (~1 s ใน 2 s)', t1 > 0.7 && t1 < 1.4, `t=${t1.toFixed(2)}`)
await page.click('[data-testid=play]')

// count-in: ช่วงนับ เวลาเพลงต้องอยู่ที่จุดเริ่ม
await page.select('[data-testid=rate]', '1')
await sleep(300)
await page.select('[data-testid=countin]', '2')
await page.evaluate(async () => window.__getTransport().seek(0))
await page.click('[data-testid=play]')
await sleep(250)
const tc = await tm()
check('ระหว่างนับ เวลาเพลงยังไม่เดิน', tc < 0.05, `t=${tc.toFixed(3)}`)
await sleep(2500)
check('หลังนับ เพลงเดินแล้ว', (await tm()) > 0.2)
await page.click('[data-testid=play]')
await page.select('[data-testid=countin]', '0')

// loop
await page.evaluate(async () => { const t = window.__getTransport(); t.seek(2) })
await page.click('[data-testid=loop-a]')
await page.evaluate(async () => { window.__getTransport().seek(3) })
await page.click('[data-testid=loop-b]')
await page.click('[data-testid=play]')
let max = 0, min = 99
for (let i = 0; i < 30; i++) { const t = await tm(); max = Math.max(max, t); min = Math.min(min, t); await sleep(150) }
check('loop 2–3 s: เวลาไม่เกิน B และวนกลับมาที่ A', max < 3.3 && min >= 1.9, `min=${min.toFixed(2)} max=${max.toFixed(2)}`)
await page.click('[data-testid=play]')
check('ไม่มี console error', errors.length === 0, errors.join(' | '))
await browser.close()
process.exit(failed ? 1 : 0)
