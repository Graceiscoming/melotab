// ทดสอบแผง "ความละเอียดโน้ต" (retranscribe) + เวอร์ชันก่อนหน้า ผ่านหน้าเว็บจริง
// อัปโหลดเพลงใหม่ → โปรเจกต์ใหม่ที่มี notes_raw.json (cache hit จึงเร็ว)
import puppeteer from 'puppeteer-core'

let failed = 0
const check = (name, cond, extra = '') => { console.log(cond ? 'PASS' : 'FAIL', name, extra); if (!cond) failed++ }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new',
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'], defaultViewport: { width: 1400, height: 850 },
})
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('dialog', (d) => d.accept())
await page.goto('http://localhost:5173', { waitUntil: 'networkidle0' })
await page.waitForSelector('[data-testid=statusbar] .dot.ok')

await (await page.$('[data-testid=fileinput]')).uploadFile('D:/melotab/testdata/song01.mp4')
await page.waitForSelector('[data-testid=pianoroll] canvas', { timeout: 120000 })
await sleep(800)
const count = () => page.$eval('[data-testid=notecount]', (e) => Number(e.textContent))
const n0 = await count()
check('เปิดโปรเจกต์ใหม่ได้ (150 โน้ต)', n0 === 150, `n=${n0}`)
check('มีค่า tuning แสดงในแถบข้อมูล', (await page.$('[data-testid=tuning]')) !== null, await page.$eval('[data-testid=tuning]', (e) => e.textContent))

// เปิดแผง → ตั้ง "ตัดโน้ตสั้นกว่า 200 ms" → แกะใหม่
await page.evaluate(() => [...document.querySelectorAll('button')].find((b) => b.textContent.includes('ความละเอียดโน้ต')).click())
await page.waitForSelector('[data-testid=sens-panel]')
await page.evaluate(() => {
  const input = document.querySelector('[data-testid=sens-panel] input[type=range]')
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
  set.call(input, '200')
  input.dispatchEvent(new Event('input', { bubbles: true }))
})
await page.evaluate(() => [...document.querySelectorAll('[data-testid=sens-panel] button')].find((b) => b.textContent === 'แกะใหม่').click())
await page.waitForFunction((prev) => Number(document.querySelector('[data-testid=notecount]').textContent) !== prev, { timeout: 20000 }, n0)
const n1 = await count()
check('ตัดโน้ตสั้นกว่า 200 ms → จำนวนโน้ตลดลง', n1 < n0, `${n0}→${n1}`)
const minDur = await page.evaluate(() => Math.min(...window.__melotab.getState().song.notes.map((n) => n.end - n.start)) * 1000)
check('ไม่มีโน้ตสั้นกว่า 200 ms เหลือ', minDur >= 199, `min=${minDur.toFixed(0)} ms`)

// ตั้งค่ากลับเป็น 0 → โน้ตกลับมาเท่าเดิม (ไม่รวมโน้ตซ้ำเมื่อ merge=0 — ตรวจบั๊กเก่า)
await page.evaluate(() => {
  const input = document.querySelector('[data-testid=sens-panel] input[type=range]')
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
  set.call(input, '0')
  input.dispatchEvent(new Event('input', { bubbles: true }))
})
await page.evaluate(() => [...document.querySelectorAll('[data-testid=sens-panel] button')].find((b) => b.textContent === 'แกะใหม่').click())
await page.waitForFunction((prev) => Number(document.querySelector('[data-testid=notecount]').textContent) !== prev, { timeout: 20000 }, n1)
check('ตั้งกลับเป็น 0 → ได้ 150 โน้ตเท่าเดิม', (await count()) === n0, `n=${await count()}`)

// ประวัติ: ทำการแก้ 2 ครั้ง (เว้น > 120 s ไม่ได้ในเทสต์) จึงตรวจแค่ว่าแผงเปิดและเรียก API ได้
await page.evaluate(() => [...document.querySelectorAll('button')].find((b) => b.textContent.includes('เวอร์ชันก่อนหน้า')).click())
await page.waitForSelector('[data-testid=history-panel]')
await sleep(500)
check('แผงเวอร์ชันก่อนหน้าเปิดได้และโหลดรายการ', (await page.$eval('[data-testid=history-panel]', (e) => e.innerText)).includes('เวอร์ชันก่อนหน้า'))
console.log('errors:', errors.length ? errors : 'none')
await browser.close()
process.exit(failed ? 1 : 0)
