// ทดสอบ Chord Sheet / คอร์ด / ท่อน / เนื้อร้อง บนหน้าเว็บจริง (ต้องรัน backend :8000 + vite :5173 และโปรเจกต์ song02 ที่วิเคราะห์ด้วย chords แล้ว)
// หมายเหตุ: เนื้อที่วางในเทสต์เป็นข้อความสังเคราะห์ที่แต่งขึ้นเอง ไม่ใช่เนื้อเพลงจริง; ผล ASR ตรวจแค่จำนวน ไม่พิมพ์เนื้อหา
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
  return ps.filter((p) => p.analyzed && /song02/.test(p.title)).sort((a, b) => b.created - a.created)[0].id
})
await page.evaluate((id) => window.__melotab.getState().openProject(id), pid)
await page.waitForSelector('[data-testid=pianoroll] canvas')
await sleep(1200)
const G = () => page.evaluate(() => { const s = window.__melotab.getState(); return { song: s.song, mode: s.view.mode } })
let g = await G()
check('โปรเจกต์มีคอร์ด/ท่อน/คีย์เปลี่ยน (จากการวิเคราะห์)', g.song.chords?.length > 20 && g.song.sections?.length >= 2 && Array.isArray(g.song.key_changes), `chords=${g.song.chords?.length} sections=${g.song.sections?.length}`)
check('คอร์ดทุกตัวเริ่มตรง beat (smoothing)', g.song.chords.every((c) => c.start_beat >= g.song.beats.length || Math.abs(c.start - g.song.beats[c.start_beat].time) < 0.02))
await page.screenshot({ path: `${OUT}/12-roll-strips.png` })

// 1) เข้า Chord Sheet
await page.click('[data-testid=mode-sheet]')
await page.waitForSelector('[data-testid=sheet-row]')
const rows = await page.$$eval('[data-testid=sheet-row]', (r) => r.length)
const chordsShown = await page.$$eval('[data-testid=sheet-chord]', (c) => c.map((x) => x.textContent))
check('Chord Sheet แสดงแถวและคอร์ด', rows >= 5 && chordsShown.length > 20, `rows=${rows} chords=${chordsShown.length}`)
const nonN = g.song.chords.filter((c) => c.symbol !== 'N').length
check('จำนวนคอร์ดบนใบ = จำนวนคอร์ดในข้อมูล (ไม่หาย/ไม่ซ้ำ)', chordsShown.length === nonN, `${chordsShown.length}/${nonN}`)
await page.screenshot({ path: `${OUT}/13-chordsheet.png` })

// 2) คลิกคอร์ด → ไดอะแกรม
await page.click('[data-testid=sheet-chord]')
await page.waitForSelector('[data-testid=chord-diagram]', { timeout: 5000 })
const diag = await page.$eval('[data-testid=chord-diagram]', (e) => e.getAttribute('data-symbol'))
check('คลิกคอร์ดแสดงไดอะแกรมทรง', !!diag, diag)
await page.mouse.click(5, 300)    // ปิด popover
await sleep(200)

// 3) transpose / capo
const first = chordsShown[0]
await page.click('[data-testid=tr-plus]'); await page.click('[data-testid=tr-plus]')
await sleep(200)
const afterTr = await page.$eval('[data-testid=sheet-chord]', (e) => e.textContent)
check('transpose +2 เปลี่ยนคอร์ด', afterTr !== first && (await page.$eval('[data-testid=tr-val]', (e) => e.textContent)) === '+2', `${first} → ${afterTr}`)
await page.click('[data-testid=tr-minus]'); await page.click('[data-testid=tr-minus]')
await sleep(200)
check('transpose กลับ 0 ได้คอร์ดเดิม', (await page.$eval('[data-testid=sheet-chord]', (e) => e.textContent)) === first)
await page.$eval('[data-testid=sheet-capo]', (el) => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(el, '2'); el.dispatchEvent(new Event('input', { bubbles: true })) })
await sleep(250)
const withCapo = await page.$eval('[data-testid=sheet-chord]', (e) => e.textContent)
check('capo 2 แสดงรูปมือต่ำลง 2 semitone (D → C)', first === 'D' ? withCapo === 'C' : withCapo !== first, `${first} → ${withCapo}`)
await page.$eval('[data-testid=sheet-capo]', (el) => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(el, '0'); el.dispatchEvent(new Event('input', { bubbles: true })) })

// 4) แก้คอร์ดด้วยดับเบิลคลิก แล้วคืนค่าเดิม
const c0 = g.song.chords.find((c) => c.symbol !== 'N')
await page.evaluate(() => { const el = document.querySelector('[data-testid=sheet-chord]'); el.dispatchEvent(new MouseEvent('dblclick', { bubbles: true })) })
await page.waitForSelector('.chordedit')
await page.keyboard.down('Control'); await page.keyboard.press('KeyA'); await page.keyboard.up('Control')
await page.keyboard.type('F#m7')
await page.keyboard.press('Enter')
await sleep(300)
g = await G()
const edited = g.song.chords.find((c) => Math.abs(c.start - c0.start) < 1e-6)
check('แก้คอร์ดแล้วบันทึกลง song (edited)', edited.symbol === 'F#m7' && edited.edited === true, edited.symbol)
await page.evaluate((c) => window.__melotab.getState().patchSong((s) => ({ ...s, chords: s.chords.map((x) => (Math.abs(x.start - c.start) < 1e-6 ? c : x)) })), c0)

// 5) ท่อน: เปลี่ยนชื่อ
await page.click('[data-testid=open-sections]')
await page.waitForSelector('[data-testid=sec-label]')
const secLabel0 = g.song.sections[0].label
await page.click('[data-testid=sec-label]')
await page.keyboard.down('Control'); await page.keyboard.press('KeyA'); await page.keyboard.up('Control')   // clickCount:3 ของ puppeteer ไม่เลือกทั้งช่อง
await page.keyboard.type('Intro-Test')
await sleep(250)
g = await G()
check('เปลี่ยนชื่อท่อนได้ และติดธง auto=false', g.song.sections[0].label === 'Intro-Test' && g.song.sections[0].auto === false)
await page.evaluate((l) => window.__melotab.getState().patchSong((s) => ({ ...s, sections: s.sections.map((x, i) => (i === 0 ? { ...x, label: l, auto: true } : x)) })), secLabel0)
await page.click('[data-testid=open-sections]')

// 6) เนื้อร้อง: วางข้อความสังเคราะห์ → จัดเวลา
await page.click('[data-testid=open-lyrics]')
await page.waitForSelector('[data-testid=lyrics-text]')
await page.$eval('[data-testid=lyrics-text]', (el) => { el.value = ''; })
await page.type('[data-testid=lyrics-text]', 'alpha beta gamma delta\nepsilon zeta eta theta\niota kappa lambda mu')
await page.click('[data-testid=align-btn]')
await page.waitForFunction(() => window.__melotab.getState().song?.lyrics?.source === 'pasted', { timeout: 15000 })
await sleep(500)
g = await G()
const lines = g.song.lyrics.lines
check('จัดเวลาเนื้อที่วางได้ 3 บรรทัด เวลาเรียงต่อกัน', lines.length === 3 && lines.every((l, i) => i === 0 || l.start >= lines[i - 1].start), `${lines.map((l) => l.start.toFixed(1)).join(', ')}`)
check('คำถูกผูกกับโน้ต (note_ids)', lines.flatMap((l) => l.words).some((w) => (w.note_ids ?? []).length > 0))
const lyricRows = await page.$$eval('[data-testid=sheet-row].lyric', (r) => r.length)
check('Chord Sheet แสดงบรรทัดเนื้อพร้อมคอร์ดเหนือคำ', lyricRows === 3 && (await page.$$eval('[data-testid=sheet-row].lyric .slot .chords .chordtag', (c) => c.length)) > 0, `lyric rows=${lyricRows}`)
await page.screenshot({ path: `${OUT}/14-sheet-lyrics.png` })

// 7) ASR จริงผ่านงานในคิว (โมเดล small เพื่อความเร็ว) — ตรวจเฉพาะจำนวน ไม่พิมพ์เนื้อหา
await page.select('[data-testid=lyrics-panel] select', 'small')
await page.evaluate(() => { window.__melotab.getState().patchSong((s) => ({ ...s, lyrics: undefined })) })
await page.evaluate(() => [...document.querySelectorAll('[data-testid=lyrics-panel] button')].find((b) => b.textContent.includes('ถอดเสียง')).click())
await page.waitForFunction(() => window.__melotab.getState().song?.lyrics?.source === 'asr', { timeout: 300000 })
await sleep(800)
g = await G()
const asrLines = g.song.lyrics.lines
const asrWords = asrLines.reduce((n, l) => n + l.words.length, 0)
check('ASR จริงผ่านงานในคิว: ได้เนื้อหลายบรรทัด/คำ', asrLines.length >= 10 && asrWords >= 100, `lines=${asrLines.length} words=${asrWords} lang=${g.song.lyrics.language}`)
check('เวลาของคำจาก ASR เรียงและไม่ซ้อนย้อนกลับ', asrLines.every((l) => l.words.every((w) => w.end >= w.start)) && asrLines.every((l, i) => i === 0 || l.start >= asrLines[i - 1].start - 0.5))
await page.waitForSelector('[data-testid=sheet-row].lyric')
await page.screenshot({ path: `${OUT}/15-sheet-asr.png` })
// เก็บกวาดไม่จำเป็น (เนื้อ ASR ใช้งานต่อได้) — ลบเนื้อทดสอบออกจากโปรเจกต์ทดสอบเพื่อไม่ให้ค้าง
await page.evaluate(async () => { window.__melotab.getState().patchSong((s) => ({ ...s, lyrics: undefined })); await window.__melotab.getState().saveNow() })
console.log('errors:', errors.length ? errors : 'none')
await browser.close()
process.exit(failed ? 1 : 0)
