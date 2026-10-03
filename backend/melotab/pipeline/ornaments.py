"""ตรวจ ornament ของเสียงร้องจากเส้น f0 ภายในโน้ต/ระหว่างโน้ต (plan หัวข้อ 12) — Phase 5

ได้ tag ต่อโน้ต: vibrato, scoop_in, fall_off, bend_up, และ "ความสัมพันธ์กับโน้ตถัดไป" slide_next / legato_next
เกณฑ์ทั้งหมดเป็น heuristic ตั้งเอง (ยังไม่ได้วัดกับเพลงที่แกะมือ) — ผู้ใช้แก้เทคนิคในแทปเองได้เสมอ

หน่วย: f0 เป็น MIDI ทศนิยม (nan = ไม่มีเสียง), เวลาเป็นวินาที, cents = 1/100 semitone
"""
from __future__ import annotations

import warnings

import numpy as np

warnings.filterwarnings("ignore", message="All-NaN slice", category=RuntimeWarning)

VIB_MIN_DUR = 0.28          # โน้ตสั้นกว่านี้ไม่นับ vibrato
VIB_RATE = (3.5, 9.0)       # Hz
VIB_MIN_DEPTH_CENTS = 35.0  # peak-to-peak ขั้นต่ำ
EDGE_S = 0.12               # หน้าต่างต้น/ท้ายโน้ตสำหรับ scoop/fall
SCOOP_MIN_CENTS = 70.0
BEND_MIN_CENTS = 60.0
GAP_MAX_S = 0.08            # ช่องว่างระหว่างโน้ตที่ยังนับว่าต่อเนื่อง
SLIDE_MIN_TRANSIT_S = 0.07  # ช่วงเปลี่ยนพิทช์ช้ากว่านี้ = slide, เร็วกว่า = legato (hammer/pull)
LEGATO_MAX_ST = 4


def _slice(t: np.ndarray, f: np.ndarray, a: float, b: float) -> np.ndarray:
    i, j = np.searchsorted(t, a), np.searchsorted(t, b)
    return f[i:j]


def _vibrato(seg: np.ndarray, hop: float) -> dict | None:
    v = seg[~np.isnan(seg)]
    if len(v) * hop < VIB_MIN_DUR or len(v) < 0.8 * len(seg):
        return None
    k = max(3, int(round(0.25 / hop)) | 1)                              # trend ช้า ๆ ออก ให้เหลือเฉพาะการสั่น
    pad = np.pad(v, k // 2, mode="edge")
    trend = np.convolve(pad, np.ones(k) / k, mode="valid")
    d = (v - trend) * 100.0
    core = d[len(d) // 8: len(d) - len(d) // 8] if len(d) > 16 else d
    if len(core) < 6:
        return None
    depth = float(np.percentile(core, 95) - np.percentile(core, 5))
    s = np.sign(core - np.median(core))
    s = s[s != 0]
    crossings = int(np.sum(s[1:] != s[:-1])) if len(s) > 1 else 0
    rate = crossings / 2.0 / (len(core) * hop)
    if depth >= VIB_MIN_DEPTH_CENTS and VIB_RATE[0] <= rate <= VIB_RATE[1] and crossings >= 4:
        return {"type": "vibrato", "rate_hz": round(rate, 1), "depth_cents": int(round(depth))}
    return None


def detect_note(note: dict, t: np.ndarray, f: np.ndarray, hop: float) -> list[dict]:
    seg = _slice(t, f, note["start"], note["end"])
    if len(seg) < 4 or np.isnan(seg).mean() > 0.4:
        return []
    out: list[dict] = []
    n = len(seg)
    ref = float(np.nanmedian(seg[n // 4: max(n // 4 + 1, 3 * n // 4)]))      # ระดับ "ตั้งใจร้อง" = ช่วงกลางโน้ต
    ne = max(2, int(round(EDGE_S / hop)))
    head = seg[:ne]
    tail = seg[-ne:]
    vib = _vibrato(seg, hop)
    if vib:
        out.append(vib)
    if not np.isnan(head).all():
        dh = (float(np.nanmedian(head)) - ref) * 100
        if dh <= -SCOOP_MIN_CENTS:
            out.append({"type": "scoop_in", "from_cents": int(round(dh)), "dur_ms": int(round(ne * hop * 1000))})
    if not np.isnan(tail).all():
        dt_ = (float(np.nanmedian(tail)) - ref) * 100
        if dt_ <= -SCOOP_MIN_CENTS * 1.4:
            out.append({"type": "fall_off", "cents": int(round(dt_)), "dur_ms": int(round(ne * hop * 1000))})
    if not vib and n >= 8:                                                    # bend = ไต่ขึ้นทางเดียวจากต้นถึงท้ายโน้ต
        a = float(np.nanmedian(seg[: n // 3]))
        b = float(np.nanmedian(seg[-(n // 3):]))
        mono = np.nanmean(np.diff(seg[~np.isnan(seg)][:: max(1, n // 12)]) >= -0.05)
        if (b - a) * 100 >= BEND_MIN_CENTS and mono > 0.8 and not any(o["type"] == "scoop_in" for o in out):
            out.append({"type": "bend_up", "cents": int(round((b - a) * 100))})
    return out


def detect_transition(a: dict, b: dict, t: np.ndarray, f: np.ndarray, hop: float) -> dict | None:
    """โน้ต a → b ต่อเนื่องไหม: คืน {"type": "slide_next"|"legato_next", "interval": semitone}"""
    gap = b["start"] - a["end"]
    interval = b["midi"] - a["midi"]
    if gap > GAP_MAX_S or interval == 0 or abs(interval) > 12:
        return None
    lo, hi = min(a["end"], b["start"]) - 0.06, max(a["end"], b["start"]) + 0.06
    seg = _slice(t, f, lo, hi)
    if len(seg) < 4 or np.isnan(seg).any():                                   # f0 ขาด = มีการเริ่มเสียงใหม่ ไม่ใช่ลากต่อ
        return None
    pa = float(np.nanmedian(_slice(t, f, a["end"] - 0.1, a["end"] - 0.02)) if len(_slice(t, f, a["end"] - 0.1, a["end"] - 0.02)) else a["midi"])
    pb = float(np.nanmedian(_slice(t, f, b["start"] + 0.02, b["start"] + 0.1)) if len(_slice(t, f, b["start"] + 0.02, b["start"] + 0.1)) else b["midi"])
    span = pb - pa
    if abs(span) < 0.5:
        return None
    # ความยาวช่วงเปลี่ยน: เฟรมที่อยู่ระหว่าง 15%–85% ของระยะทั้งหมด
    frac = (seg - pa) / span
    transit = float(np.sum((frac > 0.15) & (frac < 0.85))) * hop
    kind = "slide_next" if transit >= SLIDE_MIN_TRANSIT_S else "legato_next"
    if kind == "legato_next" and abs(interval) > LEGATO_MAX_ST:
        kind = "slide_next" if transit >= 0.04 else None
    return {"type": kind, "interval": int(interval), "transit_ms": int(round(transit * 1000))} if kind else None


def detect_ornaments(notes: list[dict], times: np.ndarray, midi_f0: np.ndarray, hop_s: float) -> dict[str, list[dict]]:
    """คืน {note_id: [ornament,...]} (เฉพาะโน้ตที่มี ornament)"""
    order = sorted(notes, key=lambda n: n["start"])
    res: dict[str, list[dict]] = {}
    for i, n in enumerate(order):
        orn = detect_note(n, times, midi_f0, hop_s)
        if i + 1 < len(order):
            tr = detect_transition(n, order[i + 1], times, midi_f0, hop_s)
            if tr:
                orn.append(tr)
        if orn:
            res[n["id"]] = orn
    return res


def load_f0_midi(npz_path) -> tuple[np.ndarray, np.ndarray, float]:
    z = np.load(npz_path)
    hz, t = z["f0_hz"], z["times"]
    midi = np.where(hz > 0, 69 + 12 * np.log2(np.maximum(hz, 1e-3) / 440.0), np.nan)
    return t, midi, float(z["hop_s"])
