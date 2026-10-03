"""CLI: ไฟล์เสียง/วิดีโอ → โฟลเดอร์โปรเจกต์ (song.json + melody.mid + stems)

    python -m melotab.cli analyze เพลง.mp3 --out Projects/ชื่อ [--karaoke] [--dereverb]

ลิงก์ YouTube ยังไม่รองรับในขั้นนี้ (yt-dlp ติด 403 บนเครื่องนี้ ใช้ไฟล์ที่โหลดมาเองไปก่อน)
"""
import argparse
from pathlib import Path

from .analysis import run_analysis


def analyze(src: Path, out: Path, karaoke: bool = False, dereverb: bool = False, log=print) -> dict:
    def on_event(e: dict) -> None:
        if e["type"] == "job.stage" and e["status"] != "start":
            tag = " (จาก cache)" if e["status"] == "cached" else ""
            log(f"[{e['stage_index']}/{e['stage_total']}] {e['stage']} เสร็จใน {e['seconds']} s{tag}  รวม {e['overall_pct']}%")

    song = run_analysis(src, out, karaoke=karaoke, dereverb=dereverb, on_event=on_event)
    k = song["key"]
    log(f"บันทึกแล้ว: {out / 'song.json'} ({len(song['notes'])} โน้ต, key={k and k['tonic'] + ' ' + k['mode']}, bpm={song['tempo']['bpm']})")
    return song


def main() -> None:
    ap = argparse.ArgumentParser(prog="melotab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="วิเคราะห์ไฟล์เสียง")
    a.add_argument("audio", type=Path)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--karaoke", action="store_true", help="ตัดเสียงประสาน (ช้า ~2 นาที/เพลง)")
    a.add_argument("--dereverb", action="store_true", help="ลบ reverb จาก lead (ช้า ~1 นาที/เพลง)")
    args = ap.parse_args()
    if args.cmd == "analyze":
        analyze(args.audio, args.out, args.karaoke, args.dereverb)


if __name__ == "__main__":
    main()
