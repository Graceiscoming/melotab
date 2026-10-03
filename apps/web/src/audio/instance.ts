import { Transport } from './transport'

let t: Transport | null = null

/** Transport ตัวเดียวของแอป (สร้างตอนใช้ครั้งแรก เพราะ AudioContext ควรเริ่มหลังผู้ใช้โต้ตอบ) */
export function getTransport(): Transport {
  if (!t) t = new Transport()
  return t
}
