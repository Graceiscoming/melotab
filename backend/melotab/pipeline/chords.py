"""คอร์ดจาก instrumental: BTC (โปรเซสแยก) → ชื่อคอร์ดมาตรฐาน → smoothing ตาม beat grid → slash chord จากย่านเบส

ข้อจำกัดที่ต้องรู้:
- BTC ไม่ให้ค่า confidence (ได้แค่คลาสที่เลือก) จึงไม่มี confidence ของคอร์ด
- slash chord ประเมินจากพลังงาน CQT ย่านเบส (C1–B3) ของ instrumental stem — heuristic ไม่ได้แยก bass stem ด้วยโมเดล
- ความถูกต้องของคอร์ดยังไม่เคยวัดกับ ground truth (WCSR ตามแผนหัวข้อ 24 ต้องมีไฟล์ .lab ที่แกะมือ)
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from ..config import ROOT, THIRD_PARTY

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#", "Cb": "B", "Fb": "E", "E#": "F", "B#": "C"}

# quality ของ BTC → (ต่อท้ายชื่อ, ช่วงเสียงของคอร์ด (semitone จาก root))
QUALITY = {
    "maj": ("", (0, 4, 7)), "min": ("m", (0, 3, 7)), "7": ("7", (0, 4, 7, 10)), "maj7": ("maj7", (0, 4, 7, 11)),
    "min7": ("m7", (0, 3, 7, 10)), "dim": ("dim", (0, 3, 6)), "aug": ("aug", (0, 4, 8)), "sus4": ("sus4", (0, 5, 7)),
    "sus2": ("sus2", (0, 2, 7)), "maj6": ("6", (0, 4, 7, 9)), "min6": ("m6", (0, 3, 7, 9)), "dim7": ("dim7", (0, 3, 6, 9)),
    "hdim7": ("m7b5", (0, 3, 6, 10)), "minmaj7": ("m(maj7)", (0, 3, 7, 11)),
}


def parse_label(label: str) -> dict | None:
    """'B:min' → {'root': 11, 'quality': 'min', 'symbol': 'Bm'}; 'N'/'X' → None (ไม่มีคอร์ด)"""
    if label in ("N", "X", ""):
        return None
    root_s, _, qual = label.partition(":")
    root_s = FLAT_TO_SHARP.get(root_s, root_s)
    if root_s not in NOTE_NAMES:
        return None
    qual = (qual or "maj").split("/")[0]
    if qual not in QUALITY:
        qual = "maj" if qual.startswith("maj") else "min" if qual.startswith("min") else "maj"
    return {"root": NOTE_NAMES.index(root_s), "quality": qual, "symbol": root_s + QUALITY[qual][0]}


def run_btc(audio: Path, voca: bool = False) -> list[tuple[float, float, str]]:
    """รัน BTC ในโปรเซสแยก คืน [(start, end, label)]"""
    btc_dir = THIRD_PARTY / "BTC"
    if not btc_dir.exists():
        raise FileNotFoundError("ไม่พบ third_party/BTC — ดึงโค้ดตามขั้นตอนใน backend/requirements.txt")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.lab"
        # โปรเซสลูกรันโดยมี cwd = third_party/BTC จึงต้องส่ง path เต็มเสมอ (path สัมพัทธ์จะหาไฟล์ไม่เจอ)
        cmd = [sys.executable, "-m", "melotab.pipeline.btc_worker", str(Path(audio).resolve()), str(out)] + (["--voca"] if voca else [])
        env = {**os.environ, "PYTHONPATH": str(ROOT / "backend"), "PYTHONIOENCODING": "utf-8"}
        r = subprocess.run(cmd, cwd=btc_dir, env=env, capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"BTC ล้มเหลว: {r.stderr.strip()[-400:]}")
        rows = []
        for line in out.read_text(encoding="utf-8").splitlines():
            a, b, lab = line.split(maxsplit=2)
            rows.append((float(a), float(b), lab.strip()))
        return rows


def smooth_to_beats(segs: list[tuple[float, float, str]], beat_times: list[float], min_beats: int = 2) -> list[dict]:
    """บังคับให้คอร์ดเปลี่ยนตรง beat: ต่อ beat เลือกคอร์ดที่ทับซ้อนมากสุด → รวมที่เท่ากัน → ดูดซับช่วงที่สั้นกว่า min_beats

    คืน [{'start_beat','end_beat','start','end','label'}] (ส่วนที่ไม่มีคอร์ด label='N')
    """
    if len(beat_times) < 2:
        return [{"start_beat": 0, "end_beat": 0, "start": s, "end": e, "label": lab} for s, e, lab in segs]
    n = len(beat_times)
    edges = list(beat_times) + [beat_times[-1] + (beat_times[-1] - beat_times[-2])]
    labels: list[str] = []
    j = 0
    for i in range(n):
        a, b = edges[i], edges[i + 1]
        score: dict[str, float] = {}
        while j > 0 and segs[j - 1][1] > a:
            j -= 1
        k = j
        while k < len(segs) and segs[k][0] < b:
            ov = min(b, segs[k][1]) - max(a, segs[k][0])
            if ov > 0:
                score[segs[k][2]] = score.get(segs[k][2], 0.0) + ov
            k += 1
        j = max(0, k - 1)
        labels.append(max(score, key=score.get) if score else "N")

    runs: list[list] = []                                    # [label, start_idx, end_idx(exclusive)]
    for i, lab in enumerate(labels):
        if runs and runs[-1][0] == lab:
            runs[-1][2] = i + 1
        else:
            runs.append([lab, i, i + 1])
    changed = True
    while changed and len(runs) > 1:                         # ดูดซับ run สั้น ๆ (flicker) เข้ากับเพื่อนบ้าน
        changed = False
        for idx, (lab, s, e) in enumerate(runs):
            if e - s >= min_beats:
                continue
            prev = runs[idx - 1] if idx > 0 else None
            nxt = runs[idx + 1] if idx + 1 < len(runs) else None
            if prev and nxt and prev[0] == nxt[0]:
                target = prev[0]
            elif prev and nxt:
                target = prev[0] if (prev[2] - prev[1]) >= (nxt[2] - nxt[1]) else nxt[0]
            else:
                target = (prev or nxt)[0]
            runs[idx][0] = target
            merged: list[list] = []
            for r in runs:
                if merged and merged[-1][0] == r[0]:
                    merged[-1][2] = r[2]
                else:
                    merged.append(r)
            runs = merged
            changed = True
            break
    out = []
    for lab, s, e in runs:
        out.append({"start_beat": s, "end_beat": e, "start": round(edges[s], 3), "end": round(edges[e], 3), "label": lab})
    return out


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    import librosa
    return librosa.load(str(path), sr=22050, mono=True)


def bass_pitch_classes(audio: tuple[np.ndarray, int], segs: list[dict]) -> list[np.ndarray]:
    """พลังงานต่อ pitch class (12 ค่า) ของย่านเบสในแต่ละช่วงคอร์ด (CQT C1..B3 จาก instrumental)"""
    import librosa

    y, sr = audio
    C = np.abs(librosa.cqt(y, sr=sr, hop_length=512, fmin=librosa.note_to_hz("C1"), n_bins=36, bins_per_octave=12))
    chroma = np.stack([C[pc::12].sum(axis=0) for pc in range(12)])                # [12, frames]
    times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=512)
    out = []
    for s in segs:
        m = (times >= s["start"]) & (times < s["end"])
        out.append(chroma[:, m].sum(axis=1) if m.any() else np.zeros(12))
    return out


def build_chords(segs: list[dict], bass: list[np.ndarray] | None = None) -> list[dict]:
    """แปลง segment → คอร์ดพร้อม root/quality/bass; slash chord เมื่อเบสเด่นชัดและเป็นโน้ตในคอร์ด"""
    chords = []
    for i, s in enumerate(segs):
        p = parse_label(s["label"])
        c = {"start_beat": s["start_beat"], "end_beat": s["end_beat"], "start": s["start"], "end": s["end"],
             "symbol": p["symbol"] if p else "N", "root": p["root"] if p else None, "quality": p["quality"] if p else None,
             "bass": None, "confidence": None}
        if p and bass is not None:
            e = bass[i]
            tot = float(e.sum())
            if tot > 0:
                pc = int(np.argmax(e))
                tones = {(p["root"] + x) % 12 for x in QUALITY[p["quality"]][1]}
                if pc != p["root"] and pc in tones and e[pc] / tot >= 0.45 and e[pc] >= 1.5 * e[p["root"]]:
                    c["bass"] = NOTE_NAMES[pc]
                    c["symbol"] = f"{p['symbol']}/{NOTE_NAMES[pc]}"
        chords.append(c)
    return chords


def analyze_chords(instrumental: Path, beat_times: list[float], voca: bool = False, min_beats: int = 2,
                   raw: list | None = None, audio: tuple[np.ndarray, int] | None = None) -> list[dict]:
    raw = [tuple(r) for r in raw] if raw is not None else run_btc(instrumental, voca=voca)
    segs = smooth_to_beats(raw, beat_times, min_beats=min_beats)
    return build_chords(segs, bass_pitch_classes(audio or load_audio(instrumental), segs))
