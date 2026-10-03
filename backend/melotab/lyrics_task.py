"""งานเนื้อร้อง (รันในคิวเดียวกับการวิเคราะห์): ASR บนเสียงร้องนำ → เนื้อที่ผู้ใช้วางเอง (ถ้ามี) จัดเวลา → ผูกกับโน้ต → เก็บใน song.json

ผล ASR ดิบ (คำ + เวลา) เก็บที่ analysis/asr_words.json เพื่อให้ "วางเนื้อใหม่/แก้เนื้อ" จัดเวลาได้ทันทีโดยไม่รัน ASR ซ้ำ
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from .analysis import Cancelled
from .pipeline import lyrics as L

ASR_FILE = "asr_words.json"
STAGES = ["asr", "align"]


def pick_vocal_stem(project_dir: Path) -> Path:
    for name in ("lead_dry", "lead", "vocals"):
        p = project_dir / "audio" / "stems" / f"{name}.flac"
        if p.exists():
            return p
    raise FileNotFoundError("ไม่พบเสียงร้องของโปรเจกต์ — ต้องวิเคราะห์เพลงก่อน")


def build_lyrics(song: dict, asr: dict | None, text: str | None) -> dict:
    """ประกอบก้อน lyrics ของ song.json จากผล ASR และ/หรือเนื้อที่วางเอง"""
    words = [w for s in (asr or {}).get("segments", []) for w in s["words"]]
    notes = song.get("notes", [])
    if text and text.strip():
        span = (notes[0]["start"], notes[-1]["end"]) if notes else None
        lines = L.align_pasted([l for l in text.splitlines() if l.strip()], words, span=span)
        source = "pasted"
    elif asr:
        lines = L.lines_from_asr(asr["segments"])
        source = "asr"
    else:
        raise ValueError("ไม่มีทั้งผล ASR และเนื้อที่วางเอง")
    return {"language": (asr or {}).get("language"), "source": source, "model": (asr or {}).get("model"),
            "text": text if source == "pasted" else None, "lines": L.attach_notes(lines, notes)}


def run_lyrics(project_dir: Path, save_song: Callable[[dict], None], *, text: str | None = None, model_size: str = "large-v3",
               language: str | None = None, force_asr: bool = False,
               on_event: Callable[[dict], None] = lambda e: None, cancelled: Callable[[], bool] = lambda: False) -> dict:
    song = json.loads((project_dir / "song.json").read_text(encoding="utf-8"))
    asr_path = project_dir / "analysis" / ASR_FILE
    done_w = 0.0
    weights = {"asr": 90.0, "align": 10.0}

    def stage(name: str, idx: int):
        if cancelled():
            raise Cancelled()
        on_event({"type": "job.stage", "stage": name, "stage_index": idx, "stage_total": 2, "status": "start", "overall_pct": done_w})
        return time.time()

    def finish(name: str, idx: int, t0: float, cached: bool = False):
        nonlocal done_w
        done_w += weights[name]
        on_event({"type": "job.stage", "stage": name, "stage_index": idx, "stage_total": 2, "status": "cached" if cached else "done",
                  "seconds": round(time.time() - t0, 1), "overall_pct": done_w})

    t0 = stage("asr", 1)
    asr = None
    if asr_path.exists() and not force_asr:
        cached = json.loads(asr_path.read_text(encoding="utf-8"))
        if cached.get("model") == model_size and (language is None or cached.get("language") == language):
            asr = cached
    if asr is None:
        asr = L.transcribe_asr(pick_vocal_stem(project_dir), model_size=model_size, language=language)
        asr["model"] = model_size
        asr_path.parent.mkdir(parents=True, exist_ok=True)
        asr_path.write_text(json.dumps(asr, ensure_ascii=False), encoding="utf-8")
        finish("asr", 1, t0)
    else:
        finish("asr", 1, t0, cached=True)

    t0 = stage("align", 2)
    song["lyrics"] = build_lyrics(song, asr, text)
    save_song(song)
    finish("align", 2, t0)
    return song


def realign(project_dir: Path, save_song: Callable[[dict], None], text: str) -> dict:
    """จัดเวลาเนื้อที่วางใหม่จากผล ASR ที่เก็บไว้ (เร็ว ไม่รันโมเดล) — ถ้ายังไม่เคยรัน ASR จะจัดกระจายเท่า ๆ กันตามช่วงโน้ต"""
    song = json.loads((project_dir / "song.json").read_text(encoding="utf-8"))
    f = project_dir / "analysis" / ASR_FILE
    asr = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    song["lyrics"] = build_lyrics(song, asr, text)
    song["lyrics"]["aligned_with_asr"] = asr is not None
    save_song(song)
    return song
