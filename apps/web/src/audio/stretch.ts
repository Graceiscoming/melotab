// @ts-expect-error soundtouchjs ไม่มี type
import { SoundTouch, SimpleFilter, WebAudioBufferSource } from 'soundtouchjs'

/** ยืด/หดเวลาของ AudioBuffer โดยไม่เปลี่ยน pitch (SoundTouch) — ประมวลผลเป็นชิ้น คืน event loop ให้ UI ไม่ค้าง */
export async function timeStretch(ctx: BaseAudioContext, buf: AudioBuffer, tempo: number): Promise<AudioBuffer> {
  const st = new SoundTouch()
  st.tempo = tempo
  const filter = new SimpleFilter(new WebAudioBufferSource(buf), st)
  const total = Math.ceil(buf.length / tempo) + 8192
  const out = ctx.createBuffer(2, total, buf.sampleRate)
  const L = out.getChannelData(0)
  const R = out.getChannelData(1)
  const CH = 16384
  const tmp = new Float32Array(CH * 2)
  let pos = 0
  let n: number
  while (pos < total && (n = filter.extract(tmp, CH)) > 0) {
    const m = Math.min(n, total - pos)
    for (let i = 0; i < m; i++) { L[pos + i] = tmp[2 * i]; R[pos + i] = tmp[2 * i + 1] }
    pos += m
    await new Promise((r) => setTimeout(r, 0))
  }
  const trimmed = ctx.createBuffer(2, Math.max(1, pos), buf.sampleRate)
  trimmed.copyToChannel(L.subarray(0, pos), 0)
  trimmed.copyToChannel(R.subarray(0, pos), 1)
  return trimmed
}
