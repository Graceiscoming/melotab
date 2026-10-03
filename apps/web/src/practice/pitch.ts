/** ตรวจ pitch ของเสียงเดี่ยวจากไมค์ด้วย McLeod NSDF (normalized square difference) — ใช้กับกีตาร์ E2–E6 */
export interface PitchResult { hz: number; clarity: number }

export function detectPitch(buf: Float32Array, sr: number, minHz = 70, maxHz = 1400, threshold = 0.85): PitchResult | null {
  const n = buf.length
  let energy = 0
  for (let i = 0; i < n; i++) energy += buf[i] * buf[i]
  if (Math.sqrt(energy / n) < 0.01) return null // เบาเกิน = ไม่มีเสียง
  const minLag = Math.floor(sr / maxHz)
  const maxLag = Math.min(Math.floor(sr / minHz), n >> 1)
  const nsdf = new Float32Array(maxLag + 2)
  for (let tau = 0; tau <= maxLag + 1 && tau < n; tau++) {
    let acf = 0
    let m = 0
    for (let i = 0; i < n - tau; i++) { acf += buf[i] * buf[i + tau]; m += buf[i] * buf[i] + buf[i + tau] * buf[i + tau] }
    nsdf[tau] = m > 0 ? (2 * acf) / m : 0
  }
  // ยอดแรก (หลังข้ามศูนย์ลบ) ที่สูงกว่า threshold × ยอดสูงสุด
  const peaks: number[] = []
  let pos = false
  let best = 0
  let bestTau = -1
  for (let tau = 1; tau <= maxLag; tau++) {
    if (nsdf[tau - 1] < 0 && nsdf[tau] >= 0) { pos = true; best = 0; bestTau = -1 }
    if (pos && nsdf[tau] > nsdf[tau - 1] && nsdf[tau] >= nsdf[tau + 1] && tau >= minLag) {
      if (nsdf[tau] > best) { best = nsdf[tau]; bestTau = tau }
    }
    if (pos && nsdf[tau] < 0 && bestTau > 0) { peaks.push(bestTau); pos = false; bestTau = -1 }
  }
  if (pos && bestTau > 0) peaks.push(bestTau)
  if (!peaks.length) return null
  const top = Math.max(...peaks.map((p) => nsdf[p]))
  const tau = peaks.find((p) => nsdf[p] >= threshold * top)!
  if (nsdf[tau] < 0.6) return null
  // ประมาณค่ายอดแบบพาราโบลาให้ละเอียดกว่า 1 ตัวอย่าง
  const a = nsdf[tau - 1]
  const b = nsdf[tau]
  const c = nsdf[tau + 1]
  const denom = a - 2 * b + c
  const shift = denom !== 0 ? (0.5 * (a - c)) / denom : 0
  return { hz: sr / (tau + shift), clarity: nsdf[tau] }
}

export const hzToMidi = (hz: number) => 69 + 12 * Math.log2(hz / 440)
