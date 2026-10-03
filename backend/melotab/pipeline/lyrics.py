"""เนื้อร้อง: faster-whisper (timestamp ระดับคำ) บนเสียงร้องนำ + จัดเวลาเนื้อที่ผู้ใช้วางเอง + ผูกคำเข้ากับโน้ต

ข้อจำกัดที่ต้องรู้ (plan หัวข้อ 6 ขั้น [9] และ 25):
- Whisper ถอดเสียงร้องเพลงพลาดได้มาก โดยเฉพาะภาษาไทย → ให้ผู้ใช้วางเนื้อที่ถูกต้องเอง
- "การจัดเวลาเนื้อที่วางเอง" ที่นี่เป็นการ **เทียบลำดับตัวอักษรกับผล ASR** (difflib) แล้วถ่ายเวลา + interpolate ส่วนที่ไม่ตรง
  ไม่ใช่ forced alignment ด้วยโมเดลเสียง (WhisperX ใช้ไม่ได้ เพราะต้องการ torch 2.8 ชนกับ torch ใน venv หลัก) ความแม่นระดับคำจึงหยาบกว่า
- timestamp ระดับคำของ Whisper เองก็ไม่แม่นเท่า forced alignment โดยเฉพาะเสียงลากยาว
"""
from __future__ import annotations

import difflib
import os
import site
from pathlib import Path

from ..config import MODELS_DIR
from ..gpu import free_gpu

MIN_CHAR_S = 0.06


def _add_cuda12_dll_dirs() -> None:
    """ctranslate2 ต้องใช้ cublas/cudnn ของ CUDA 12 — ใช้ wheel nvidia-*-cu12 ใน site-packages (torch ใน venv นี้เป็น CUDA 13)"""
    for base in site.getsitepackages():
        for sub in ("cublas", "cudnn", "cuda_nvrtc"):
            d = Path(base) / "nvidia" / sub / "bin"
            if d.exists():
                try:
                    os.add_dll_directory(str(d))
                except (AttributeError, OSError):
                    pass
                os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")


def transcribe_asr(audio: Path, model_size: str = "large-v3", language: str | None = None, device: str = "cuda") -> dict:
    """คืน {'language', 'language_probability', 'segments': [{start,end,text,words:[{text,start,end,prob}]}]}"""
    _add_cuda12_dll_dirs()
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device=device, compute_type="int8_float16" if device == "cuda" else "int8",
                         download_root=str(MODELS_DIR / "whisper"))
    try:
        segs, info = model.transcribe(str(audio), word_timestamps=True, language=language, beam_size=5,
                                      condition_on_previous_text=False, vad_filter=True)
        out = []
        for s in segs:
            words = [{"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3), "prob": round(float(w.probability), 3)}
                     for w in (s.words or []) if w.word.strip()]
            if words:
                out.append({"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(), "words": words})
    finally:
        del model
        free_gpu()
    return {"language": info.language, "language_probability": round(float(info.language_probability), 3), "segments": out}


def _is_thai(text: str) -> bool:
    return any("฀" <= c <= "๿" for c in text)


def tokenize(line: str) -> list[str]:
    """ตัดคำ: ภาษาไทยด้วย PyThaiNLP (newmm) ภาษาอื่นแยกด้วยช่องว่าง"""
    line = line.strip()
    if not line:
        return []
    if _is_thai(line):
        from pythainlp.tokenize import word_tokenize
        return [w for w in word_tokenize(line, engine="newmm", keep_whitespace=False) if w.strip()]
    return line.split()


def _char_timeline(asr_words: list[dict]) -> tuple[str, list[tuple[float, float]]]:
    """ตัวอักษร (ไม่รวมช่องว่าง) ของผล ASR ทั้งหมดพร้อมเวลา: กระจายความยาวของคำเท่า ๆ กันตามจำนวนตัวอักษร"""
    chars, times = [], []
    for w in asr_words:
        cs = [c for c in w["text"] if not c.isspace()]
        if not cs:
            continue
        d = (w["end"] - w["start"]) / len(cs)
        for i, c in enumerate(cs):
            chars.append(c)
            times.append((w["start"] + i * d, w["start"] + (i + 1) * d))
    return "".join(chars), times


def align_pasted(lines: list[str], asr_words: list[dict], span: tuple[float, float] | None = None) -> list[dict]:
    """จัดเวลาเนื้อที่ผู้ใช้วาง (ทีละบรรทัด) ด้วยการเทียบตัวอักษรกับผล ASR — คืนบรรทัดพร้อมคำและเวลา

    ตัวอักษรที่ตรงกับ ASR ได้เวลาจากผล ASR ตัวที่เหลือ interpolate ตามตำแหน่ง ถ้า ASR ว่างเปล่าจะกระจายตามจำนวนตัวอักษรใน `span`
    """
    toks = [tokenize(l) for l in lines]
    flat = [(li, w) for li, ws in enumerate(toks) for w in ws]
    pasted = "".join(w for _, w in flat)
    if not pasted:
        return []
    ref, ref_t = _char_timeline(asr_words)
    n = len(pasted)
    start = [None] * n
    end = [None] * n
    if ref:
        sm = difflib.SequenceMatcher(None, ref, pasted, autojunk=False)
        for a, b, size in sm.get_matching_blocks():
            for k in range(size):
                start[b + k], end[b + k] = ref_t[a + k]
    known = [i for i in range(n) if start[i] is not None]
    lo, hi = (span or ((ref_t[0][0], ref_t[-1][1]) if ref_t else (0.0, float(n) * 0.2)))
    if not known:                                              # ไม่มีส่วนที่ตรงเลย (หรือไม่มี ASR) → กระจายเท่า ๆ กันตามตัวอักษร
        d = (hi - lo) / n
        for i in range(n):
            start[i], end[i] = lo + i * d, lo + (i + 1) * d
    else:
        first, last = known[0], known[-1]
        for i in range(first):                                  # ก่อนตัวแรกที่ตรง: ถอยหลังด้วยความยาวต่อตัวอักษรขั้นต่ำ
            start[i] = max(0.0, start[first] - (first - i) * 0.12)
            end[i] = start[i] + 0.12
        for i in range(last + 1, n):
            start[i] = end[last] + (i - last - 1) * 0.12
            end[i] = start[i] + 0.12
        for a, b in zip(known, known[1:]):                      # ระหว่างตัวที่ตรง: interpolate เป็นเส้นตรง
            gap = b - a - 1
            if gap > 0:
                t0, t1 = end[a], start[b]
                d = max(MIN_CHAR_S, (t1 - t0) / gap) if t1 > t0 else MIN_CHAR_S
                for k in range(gap):
                    start[a + 1 + k] = t0 + k * d
                    end[a + 1 + k] = t0 + (k + 1) * d
    for i in range(1, n):                                       # เวลาต้องไม่ย้อนกลับ
        start[i] = max(start[i], start[i - 1])
        end[i] = max(end[i], start[i] + 0.01)
    out, pos = [], 0
    for li, ws in enumerate(toks):
        words = []
        for w in ws:
            words.append({"text": w, "start": round(start[pos], 3), "end": round(max(end[pos + len(w) - 1], start[pos] + 0.02), 3)})
            pos += len(w)
        if words:
            out.append({"id": f"l{len(out) + 1}", "start": words[0]["start"], "end": words[-1]["end"],
                        "text": lines[li].strip(), "words": words})
    return out


def lines_from_asr(segments: list[dict]) -> list[dict]:
    return [{"id": f"l{i}", "start": s["start"], "end": s["end"], "text": s["text"],
             "words": [{"text": w["text"], "start": w["start"], "end": w["end"]} for w in s["words"]]}
            for i, s in enumerate(segments, 1)]


def attach_notes(lines: list[dict], notes: list[dict]) -> list[dict]:
    """ผูกแต่ละคำกับโน้ตที่ทับซ้อนเวลา (note_ids) — ใช้วางคอร์ด/คำบน piano roll และ chord sheet"""
    ns = sorted(notes, key=lambda n: n["start"])
    for ln in lines:
        for w in ln["words"]:
            w["note_ids"] = [n["id"] for n in ns if n["start"] < w["end"] and n["end"] > w["start"]]
    return lines
