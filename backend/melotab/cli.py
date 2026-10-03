"""CLI: ไฟล์เสียง/วิดีโอ → โฟลเดอร์โปรเจกต์ (song.json + melody.mid + stems)

    python -m melotab.cli analyze เพลง.mp3 --out Projects/ชื่อ [--karaoke] [--dereverb]

ลิงก์ YouTube ยังไม่รองรับในขั้นนี้ (yt-dlp ติด 403 บนเครื่องนี้ ใช้ไฟล์ที่โหลดมาเองไปก่อน)
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from . import audio
from .pipeline import f0 as f0_stage
from .pipeline import key as key_stage
from .pipeline import notes as notes_stage
from .pipeline import rhythm as rhythm_stage
from .pipeline import separation
from .song import build_song, export_midi, save_song


def analyze(src: Path, out: Path, karaoke: bool = False, dereverb: bool = False, log=print) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}

    def stage(name: str):
        class _T:
            def __enter__(self_):
                log(f"[{name}] ...")
                self_.t = time.time()
            def __exit__(self_, *a):
                timings[name] = round(time.time() - self_.t, 1)
                log(f"[{name}] เสร็จใน {timings[name]} s")
        return _T()

    with stage("ingest"):
        wav = audio.to_wav(src, out / "audio" / "source.wav")
        sha = audio.file_hash(src)
    with stage("separation"):
        stems = separation.separate(wav, out / "audio" / "stems", karaoke=karaoke, dereverb=dereverb)
    melody = stems["melody_source"]
    with stage("f0"):
        f0 = f0_stage.extract_f0(melody)
        (out / "analysis").mkdir(exist_ok=True)
        np.savez_compressed(out / "analysis" / "f0.npz", **f0)
    with stage("notes"):
        notes = notes_stage.annotate(notes_stage.transcribe(melody), f0)
    with stage("rhythm"):
        rhythm = rhythm_stage.analyze_rhythm(wav)
    key = key_stage.estimate_key(notes)

    dur = float(np.load(out / "analysis" / "f0.npz")["times"][-1])
    song = build_song(
        source={"type": "file", "path": str(src), "title": src.stem, "duration": round(dur, 1), "audio_hash": sha},
        notes=notes, rhythm=rhythm, key=key, f0_ref="analysis/f0.npz",
        meta={"karaoke": karaoke, "dereverb": dereverb, "melody_source": melody.name, "timings_s": timings},
    )
    save_song(song, out / "song.json")
    export_midi(notes, out / "melody.mid")
    log(f"บันทึกแล้ว: {out / 'song.json'} ({len(notes)} โน้ต, key={key and key['tonic'] + ' ' + key['mode']}, bpm={song['tempo']['bpm']})")
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
