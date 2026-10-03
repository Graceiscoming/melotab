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
from .pipeline import chords as chords_stage
from .pipeline import f0 as f0_stage
from .pipeline import key as key_stage
from .pipeline import notes as notes_stage
from .pipeline import rhythm as rhythm_stage
from .pipeline import separation
from .pipeline import structure as structure_stage
from .song import build_song, export_midi, save_song

# น้ำหนักเวลาโดยประมาณ (วินาที ต่อเพลง ~4 นาที) จากผลวัด Phase 0 — ใช้คำนวณ % รวมแบบหยาบ
STAGE_WEIGHT = {"ingest": 1, "separation": 35, "karaoke": 118, "dereverb": 67, "f0": 5, "notes": 4, "rhythm": 2, "chords": 8, "structure": 2}


class Cancelled(Exception):
    pass


def plan_stages(karaoke: bool, dereverb: bool) -> list[str]:
    s = ["ingest", "separation"]
    if karaoke:
        s.append("karaoke")
    if dereverb:
        s.append("dereverb")
    return s + ["f0", "notes", "rhythm", "chords", "structure"]


def run_analysis(src: Path, out: Path, *, karaoke: bool = False, dereverb: bool = False,
                 fix_octave: bool = True, min_dur_ms: float = 0.0, merge_gap_ms: float = 0.0,
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
    audio.to_preview_mp3(wav, out / "audio" / "mix.mp3")
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

    # --- notes (SOME ดิบ cache ได้; annotate/refine เบา คำนวณใหม่ทุกครั้ง) ---
    raw = cached_json("notes", lambda: notes_stage.transcribe(melody), model=SOME_CKPT.name)
    (out / "analysis" / "notes_raw.json").write_text(json.dumps(raw), encoding="utf-8")  # ให้ retranscribe ใช้ซ้ำโดยไม่รัน SOME ใหม่
    tuning = notes_stage.estimate_tuning(f0)
    notes = notes_stage.annotate(notes_stage.refine(raw, min_dur_ms=min_dur_ms, merge_gap_ms=merge_gap_ms), f0,
                                 fix_octave=fix_octave, tuning_cents=tuning)

    # --- rhythm ---
    rhythm = cached_json("rhythm", lambda: rhythm_stage.analyze_rhythm(wav), model="beat_this_final0")

    key = key_stage.estimate_key(notes)

    # --- chords: BTC (โปรเซสแยก) บน instrumental → smoothing ตาม beat → slash chord จากย่านเบส ---
    inst = stems_dir / "instrumental.flac"
    audio_inst = chords_stage.load_audio(inst)
    beat_times = [b["time"] for b in rhythm["beats"]]
    raw_chords = cached_json("chords", lambda: [list(r) for r in chords_stage.run_btc(inst)], model="btc_majmin")
    chords = chords_stage.analyze_chords(inst, beat_times, raw=raw_chords, audio=audio_inst) if beat_times else []

    # --- structure: ห้อง → เปลี่ยนคีย์ + แบ่งท่อน (heuristic) ---
    t0 = begin("structure")
    bars = structure_stage.bars_from_beats(rhythm["beats"])
    bar_t = structure_stage.bar_times(rhythm["beats"], bars) if bars else []
    key_changes = structure_stage.detect_key_changes(notes, bar_t, key) if bar_t else []
    sections: list[dict] = []
    if bar_t and chords:
        import librosa
        y, sr = audio_inst
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        rt = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
        energy = np.array([float(rms[(rt >= a) & (rt < b)].mean()) if ((rt >= a) & (rt < b)).any() else 0.0 for a, b in bar_t])
        feats = structure_stage.bar_features(chords, bar_t, energy)
        sections = structure_stage.segment_structure(feats, energy)
        for i, sec in enumerate(sections, 1):
            sec["id"] = f"s{i}"
            sec["start"] = round(bar_t[sec["start_bar"] - 1][0], 3)
            sec["end"] = round(bar_t[min(sec["end_bar"] - 2, len(bar_t) - 1)][1], 3)
    end("structure", t0, False)

    song = build_song(
        source={"type": "file", "path": str(src), "title": src.stem,
                "duration": round(float(f0["times"][-1]), 1), "audio_hash": sha},
        notes=notes, rhythm=rhythm, key=key, f0_ref="analysis/f0.npz", tuning_offset_cents=tuning,
        extra={"chords": chords, "sections": sections, "key_changes": key_changes},
        meta={"karaoke": karaoke, "dereverb": dereverb, "melody_source": melody.name, "fix_octave": fix_octave,
              "min_dur_ms": min_dur_ms, "merge_gap_ms": merge_gap_ms,
              "timings_s": timings, "cached_stages": cached_stages},
    )
    save_song(song, out / "song.json")
    export_midi(notes, out / "melody.mid")
    return song
