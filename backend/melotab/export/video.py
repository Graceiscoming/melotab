"""Video Export (plan หัวข้อ 22 ข้อ 9): วิดีโอแทปวิ่งพร้อมเพลง (MP4, H.264+AAC) สำหรับลง YouTube/TikTok

วาดแถบแทปยาวเส้นเดียวครั้งเดียว แล้วเลื่อนหน้าต่างตามเวลา (playhead อยู่กลางจอ) เฟรมละ crop + ไฮไลต์โน้ตที่กำลังเล่น + คอร์ด/เนื้อร้อง
ส่งเฟรมดิบเข้า ffmpeg ผ่าน stdin พร้อมเสียงจากไฟล์ mix ตัดตามช่วงเดียวกัน (ต้องมี ffmpeg ใน PATH)
ข้อจำกัด: เวลาเรนเดอร์ประมาณ 1–2 เท่าของความยาววิดีโอ (วาดด้วย CPU/PIL), ไม่มีโน้ตสากล, ตำแหน่งโน้ตวางตาม beat grid ที่ quantize แล้ว
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw

from .model import chord_at_beat, section_bar_range, tech_marks, time_to_beat
from .render import THEMES, Canvas, font

PX_BEAT = 136.0
STRIP_H = 210
LINE_GAP = 28


def _strip(model: dict, b0: float, b1: float, th: dict) -> tuple[Image.Image, dict[str, tuple[float, str]]]:
    """แถบแทปยาว ตั้งแต่ beat b0 ถึง b1 → (ภาพ RGBA, {note_id: x})"""
    width = int((b1 - b0) * PX_BEAT) + 40
    cv = Canvas(width, STRIP_H, {**th, "bg": None})
    top = 30
    for s in range(6):
        cv.line(0, top + s * LINE_GAP, width, top + s * LINE_GAP, th["line"], 1.4)
    for m in model["measures"]:
        if m["start_beat"] + m["beats"] < b0 or m["start_beat"] > b1:
            continue
        x = (m["start_beat"] - b0) * PX_BEAT
        cv.line(x, top, x, top + 5 * LINE_GAP, th["bar"], 2)
        cv.text(x + 4, top + 5 * LINE_GAP + 16, str(m["index"] + 1), 12, th["dim"])
    xs: dict[str, tuple[float, str]] = {}
    for e in model["events"]:
        if not (b0 - 1 <= e["beat"] <= b1 + 1):
            continue
        x = (e["beat"] - b0) * PX_BEAT + 6
        y = top + (e["string"] - 1) * LINE_GAP
        label = str(e["fret"]) + tech_marks(e["tech"])
        cv.rect(x - 13 - 5 * (len(label) - 1), y - 13, 26 + 10 * (len(label) - 1), 26, th["bg"] or "#14161b")
        cv.text(x, y + 8.5, label, 24, th["ink"], bold=True, anchor="middle")
        xs[e["note_id"]] = (x, label)
    return cv.to_image(1), xs


def render_video(model: dict, section: dict | None, out_path: Path, audio: Path | None, *, size=(1280, 720), fps: int = 15,
                 progress: Callable[[float], None] | None = None) -> dict:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ไม่พบ ffmpeg ใน PATH")
    beats = model["beats"]
    if not beats:
        raise ValueError("ไม่มี beat grid — สร้างวิดีโอไม่ได้")
    if section:
        a, b = section_bar_range(model, section)
    else:
        a, b = 0, len(model["measures"])
    ms = model["measures"][a:b]
    if not ms:
        raise ValueError("ท่อนที่เลือกไม่มีห้อง")
    b0 = float(ms[0]["start_beat"])
    b1 = float(ms[-1]["start_beat"] + ms[-1]["beats"])
    from .model import beat_to_time
    t0, t1 = beat_to_time(beats, b0), beat_to_time(beats, b1)
    th = THEMES["dark"]
    W, H = size
    strip, xs = _strip(model, b0, b1, th)
    pad = Image.new("RGBA", (strip.width + W, STRIP_H), (0, 0, 0, 0))        # เว้นขอบซ้าย/ขวาครึ่งจอให้ playhead เลื่อนถึงปลายได้
    pad.paste(strip, (W // 2, 0))
    ev = [e for e in model["events"] if b0 - 1e-6 <= e["beat"] < b1]
    lines = ((model.get("lyrics") or {}).get("lines") or [])
    f_title, f_chord, f_lyric, f_sec, f_fret = font(30, True), font(64, True), font(34), font(24, True), font(24, True)
    bg = tuple(int(th["bg"][i:i + 2], 16) for i in (1, 3, 5))
    ink = th["ink"]
    ty = H // 2 - STRIP_H // 2 + 10
    title = model["title"] or "MeloTab"
    sec_name = (section or {}).get("label", "")

    n_frames = max(1, int((t1 - t0) * fps))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(audio)]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-movflags", "+faststart", str(out_path)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fi in range(n_frames):
            t = t0 + fi / fps
            bt = time_to_beat(beats, t)
            cx = (bt - b0) * PX_BEAT + 6
            frame = Image.new("RGB", (W, H), bg)
            d = ImageDraw.Draw(frame)
            d.text((40, 56), title, fill=ink, font=f_title, anchor="ls")
            if sec_name:
                d.text((40, 92), sec_name, fill=th["accent"], font=f_sec, anchor="ls")
            c = chord_at_beat(model["chords"], bt)
            if c and c.get("symbol") not in (None, "N"):
                d.text((W - 40, 100), c["symbol"], fill=th["accent"], font=f_chord, anchor="rs")
            left = int(cx)                                                   # หน้าต่างกว้าง W กลางที่ cx (pad ซ้าย W/2)
            crop = pad.crop((left, 0, left + W, STRIP_H))
            frame.paste(crop, (0, ty), crop)
            for e in ev:                                                     # ไฮไลต์โน้ตที่กำลังเล่น (วาดทับแล้วเขียนเลขซ้ำด้วยสีเข้ม)
                if e["start"] <= t < e["end"] and e["note_id"] in xs:
                    x0, label = xs[e["note_id"]]
                    x = x0 - cx + W // 2
                    y = ty + 30 + (e["string"] - 1) * LINE_GAP
                    d.rounded_rectangle([x - 16 - 5 * (len(label) - 1), y - 15, x + 16 + 5 * (len(label) - 1), y + 15], radius=7, fill=th["accent"])
                    d.text((x, y + 8.5), label, fill=th["bg"], font=f_fret, anchor="ms")
            d.line([W // 2, ty - 6, W // 2, ty + STRIP_H - 30], fill="#ff5c7a", width=3)
            cur = next((ln for ln in lines if ln["start"] - 0.1 <= t < ln["end"] + 0.4), None)
            if cur:
                d.text((W // 2, H - 90), cur["text"], fill=ink, font=f_lyric, anchor="ms")
            proc.stdin.write(frame.tobytes())                                # type: ignore[union-attr]
            if progress and fi % fps == 0:
                progress(fi / n_frames)
        proc.stdin.close()                                                   # type: ignore[union-attr]
        err = proc.stderr.read().decode("utf-8", "replace")                  # type: ignore[union-attr]
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg ล้มเหลว: {err[-400:]}")
    except BrokenPipeError:
        raise RuntimeError(f"ffmpeg ปิดก่อนกำหนด: {proc.stderr.read().decode('utf-8', 'replace')[-400:]}")  # type: ignore[union-attr]
    finally:
        if proc.poll() is None:
            proc.kill()
    return {"frames": n_frames, "seconds": round(t1 - t0, 1), "fps": fps}
