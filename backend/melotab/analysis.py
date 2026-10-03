"""ควบคุมการวิเคราะห์ทั้งสาย: ingest → separation → f0 → notes → rhythm → ประกอบ song.json

- cache ต่อขั้น (เพลงเดิม/พารามิเตอร์เดิมไม่ต้องรันซ้ำ)
- รายงานความคืบหน้าเป็นเหตุการณ์ (`on_event`) — งานแต่ละขั้นเป็น "ก้อน" ยังไม่มี % ภายในขั้น (audio-separator/SOME ไม่ได้ให้ callback)
- ยกเลิกได้ "ระหว่างขั้น" เท่านั้น (ขั้นที่กำลังรันบน GPU ไม่ถูกขัดจังหวะกลางคัน)
"""
import json
import shutil
import time
from pathlib import Path
from typing import Callable

import numpy as np

from . import audio
from .cache import StageCache, make_key
from .config import SEP_DEREVERB_MODEL, SEP_KARAOKE_MODEL, SEP_VOCAL_MODEL, SOME_CKPT
from .pipeline import f0 as f0_stage
from .pipeline import key as key_stage
from .pipeline import notes as notes_stage
from .pipeline import rhythm as rhythm_stage
from .pipeline import separation
from .song import build_song, export_midi, save_song

# น้ำหนักเวลาโดยประมาณ (วินาที ต่อเพลง ~4 นาที) จากผลวัด Phase 0 — ใช้คำนวณ % รวมแบบหยาบ
STAGE_WEIGHT = {"ingest": 1, "separation": 35, "karaoke": 118, "dereverb": 67, "f0": 5, "notes": 4, "rhythm": 2}


class Cancelled(Exception):
    pass


def plan_stages(karaoke: bool, dereverb: bool) -> list[str]:
    s = ["ingest", "separation"]
    if karaoke:
        s.append("karaoke")
    if dereverb:
        s.append("dereverb")
    return s + ["f0", "notes", "rhythm"]


def run_analysis(src: Path, out: Path, *, karaoke: bool = False, dereverb: bool = False,
                 cache: StageCache | None = None, on_event: Callable[[dict], None] = lambda e: None,
                 cancelled: Callable[[], bool] = lambda: False) -> dict:
    cache = cache or StageCache()
    out.mkdir(parents=True, exist_ok=True)
    stages = plan_stages(karaoke, dereverb)
    total_w = sum(STAGE_WEIGHT[s] for s in stages)
    done_w = 0.0
    timings: dict[str, float] = {}
    cached_stages: list[str] = []

    def begin(name: str) -> float:
        if cancelled():
            raise Cancelled()
        on_event({"type": "job.stage", "stage": name, "stage_index": stages.index(name) + 1,
                  "stage_total": len(stages), "status": "start", "overall_pct": round(done_w / total_w * 100, 1)})
        return time.time()

    def end(name: str, t0: float, cached: bool) -> None:
        nonlocal done_w
        timings[name] = round(time.time() - t0, 1)
        if cached:
            cached_stages.append(name)
        done_w += STAGE_WEIGHT[name]
        on_event({"type": "job.stage", "stage": name, "stage_index": stages.index(name) + 1,
                  "stage_total": len(stages), "status": "cached" if cached else "done", "seconds": timings[name],
                  "overall_pct": round(done_w / total_w * 100, 1)})

    # --- ingest ---
    t0 = begin("ingest")
    wav = audio.to_wav(src, out / "audio" / "source.wav")
    sha = audio.file_hash(src)
    end("ingest", t0, False)

    # --- separation (+ karaoke/de-reverb): cache เป็นชุดเดียวตามตัวเลือก ---
    stems_dir = out / "audio" / "stems"
    sep_key = make_key("separation", sha, vocal=SEP_VOCAL_MODEL,
                       karaoke=SEP_KARAOKE_MODEL if karaoke else None,
                       dereverb=SEP_DEREVERB_MODEL if dereverb else None)
    hit = cache.get(sep_key)
    t0 = begin("separation")
    if hit:
        shutil.rmtree(stems_dir, ignore_errors=True)
        shutil.copytree(hit, stems_dir, ignore=shutil.ignore_patterns(".done", "melody.json"))
        melody = stems_dir / json.loads((hit / "melody.json").read_text())["melody"]
    else:
        stems = separation.separate(wav, stems_dir, karaoke=karaoke, dereverb=dereverb)
        melody = stems["melody_source"]
        tmp = cache.begin(sep_key)
        for p in stems_dir.glob("*.flac"):
            shutil.copy2(p, tmp / p.name)
        (tmp / "melody.json").write_text(json.dumps({"melody": melody.name}))
        cache.commit(sep_key)
    end("separation", t0, bool(hit))
    # separate() ทำ karaoke/de-reverb ภายในครั้งเดียว: แสดงเป็นขั้นแยกใน UI ตอนเสร็จแล้วเท่านั้น (ไม่มี % ภายใน)
    for name in ("karaoke", "dereverb"):
        if name in stages:
            t0 = begin(name)
            end(name, t0, bool(hit))

    base = {"sep": sep_key}

    # --- f0 (เก็บเป็น npz) ---
    f0_key = make_key("f0", sha, base=base, model="rmvpe")
    t0 = begin("f0")
    d = cache.get(f0_key)
    (out / "analysis").mkdir(exist_ok=True)
    if d:
        shutil.copy2(d / "f0.npz", out / "analysis" / "f0.npz")
    else:
        np.savez_compressed(out / "analysis" / "f0.npz", **f0_stage.extract_f0(melody))
        tmp = cache.begin(f0_key)
        shutil.copy2(out / "analysis" / "f0.npz", tmp / "f0.npz")
        cache.commit(f0_key)
    end("f0", t0, bool(d))
    z = np.load(out / "analysis" / "f0.npz")
    f0 = {"f0_hz": z["f0_hz"], "times": z["times"], "hop_s": float(z["hop_s"])}

    def cached_json(stage: str, compute, **params):
        key = make_key(stage, sha, base=base, **params)
        t0 = begin(stage)
        d = cache.get(key)
        if d:
            val = json.loads((d / "data.json").read_text(encoding="utf-8"))
        else:
            val = compute()
            tmp = cache.begin(key)
            (tmp / "data.json").write_text(json.dumps(val, ensure_ascii=False), encoding="utf-8")
            cache.commit(key)
        end(stage, t0, bool(d))
        return val

    # --- notes (SOME ดิบ cache ได้; annotate เบา คำนวณใหม่ทุกครั้ง) ---
    raw = cached_json("notes", lambda: notes_stage.transcribe(melody), model=SOME_CKPT.name)
    notes = notes_stage.annotate(raw, f0)

    # --- rhythm ---
    rhythm = cached_json("rhythm", lambda: rhythm_stage.analyze_rhythm(wav), model="beat_this_final0")

    key = key_stage.estimate_key(notes)
    song = build_song(
        source={"type": "file", "path": str(src), "title": src.stem,
                "duration": round(float(f0["times"][-1]), 1), "audio_hash": sha},
        notes=notes, rhythm=rhythm, key=key, f0_ref="analysis/f0.npz",
        meta={"karaoke": karaoke, "dereverb": dereverb, "melody_source": melody.name,
              "timings_s": timings, "cached_stages": cached_stages},
    )
    save_song(song, out / "song.json")
    export_midi(notes, out / "melody.mid")
    return song
