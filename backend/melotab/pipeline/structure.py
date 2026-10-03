"""โครงสร้างเพลง: ห้อง (bar), เปลี่ยนคีย์กลางเพลง, แบ่งท่อน (section) — Phase 4

ข้อจำกัดที่ต้องรู้ (ทั้งหมดเป็น heuristic ที่ผู้ใช้แก้ได้ใน UI):
- ไม่ได้ใช้ allin1 (ติดตั้งไม่ได้บน Windows เพราะ madmom) → แบ่งท่อนด้วย novelty ของ self-similarity ระดับห้อง
  จากคอร์ด + พลังงาน แล้วตั้งชื่อด้วยกฎง่าย ๆ (Intro/Outro/Chorus/Verse/Bridge) ไม่ได้ผ่านการวัดกับ ground truth
- key change ตรวจจากโน้ตเมโลดี้เป็นหน้าต่างเลื่อน ไม่นับการสลับ relative major/minor (กำกวมโดยธรรมชาติ)
"""
from __future__ import annotations

import numpy as np

from .key import _NAMES, estimate_key


def bars_from_beats(beats: list[dict]) -> list[tuple[int, int]]:
    """[(beat_index เริ่มห้อง, จำนวน beat)] — ห้อง pickup (ก่อน downbeat แรก) นับเป็นห้องที่ 1 เหมือนในหน้าแทป"""
    starts = [i for i, b in enumerate(beats) if b.get("beat") == 1]
    if not starts:
        return []
    bars: list[tuple[int, int]] = []
    if starts[0] > 0:
        bars.append((0, starts[0]))
    for k, s in enumerate(starts):
        nxt = starts[k + 1] if k + 1 < len(starts) else min(len(beats), s + (starts[k] - starts[k - 1] if k else 4))
        bars.append((s, max(1, nxt - s)))
    return bars


def bar_times(beats: list[dict], bars: list[tuple[int, int]]) -> list[tuple[float, float]]:
    out = []
    for s, n in bars:
        end_i = s + n
        t0 = beats[s]["time"]
        t1 = beats[end_i]["time"] if end_i < len(beats) else beats[-1]["time"] + (beats[-1]["time"] - beats[-2]["time"])
        out.append((t0, t1))
    return out


def _relative(a: dict, b: dict) -> bool:
    """major/minor ที่เป็น relative กัน (ใช้โน้ตชุดเดียวกัน) ถือเป็นคีย์เดียวกัน"""
    if a["mode"] == b["mode"]:
        return a["tonic"] == b["tonic"]
    maj, mn = (a, b) if a["mode"] == "major" else (b, a)
    return (_NAMES.index(maj["tonic"]) - 3) % 12 == _NAMES.index(mn["tonic"])


def detect_key_changes(notes: list[dict], bar_t: list[tuple[float, float]], base_key: dict | None,
                       window_bars: int = 8, hop_bars: int = 4, min_notes: int = 12, margin: float = 0.12,
                       confirm: int = 3) -> list[dict]:
    """คืน [{time, bar, tonic, mode, score}] ของคีย์ใหม่ที่ชนะคีย์ปัจจุบันเกิน `margin` (ในคะแนนสหสัมพันธ์) ติดกันอย่างน้อย `confirm` หน้าต่าง

    เทียบกับ "คะแนนของคีย์ปัจจุบัน" โดยตรง (ไม่ใช่แค่คีย์ที่ดีที่สุดในหน้าต่าง) เพราะคีย์ที่อยู่ห่างกัน 1 เครื่องหมาย (เช่น D กับ A)
    ใช้โน้ตร่วมกัน 6 จาก 7 ตัว ฮิสโทแกรมโน้ตแยกยาก — ถ้าไม่เทียบกับคีย์เดิมจะได้การเปลี่ยนคีย์ปลอมสลับไปมา
    relative major/minor ถือเป็นคีย์เดียวกัน (ใช้คะแนนที่ดีกว่าของคู่)
    """
    from .key import key_scores
    if base_key is None or len(bar_t) < window_bars + hop_bars:
        return []
    cur = (base_key["tonic"], base_key["mode"])

    def rel(k):
        t, m = k
        i = _NAMES.index(t)
        return (_NAMES[(i + 9) % 12], "minor") if m == "major" else (_NAMES[(i + 3) % 12], "major")

    wins = []
    for b0 in range(0, len(bar_t) - window_bars + 1, hop_bars):
        t0, t1 = bar_t[b0][0], bar_t[b0 + window_bars - 1][1]
        sub = [n for n in notes if t0 <= n["start"] < t1]
        wins.append((b0, t0, key_scores(sub) if len(sub) >= min_notes else {}))
    changes = []
    i = 0
    while i < len(wins):
        b0, t0, sc = wins[i]
        if not sc:
            i += 1
            continue
        cur_score = max(sc.get(cur, -1.0), sc.get(rel(cur), -1.0))
        best = max(sc, key=sc.get)
        if best in (cur, rel(cur)) or sc[best] - cur_score < margin:
            i += 1
            continue
        run = wins[i:i + confirm]
        # ผู้สมัครต้องเป็น "อันดับหนึ่ง" (หรือ relative ของมัน) ในทุกหน้าต่างที่ใช้ยืนยัน และชนะคีย์เดิมเกิน margin ทุกหน้าต่าง
        # (หน้าต่างรอยต่อที่ผสมสองคีย์มักให้คีย์ที่สามชนะชั่วคราว ต้องไม่ถูกนับเป็นการเปลี่ยนคีย์)
        def top_ok(w):
            if not w[2]:
                return False
            b = max(w[2], key=w[2].get)
            if b not in (best, rel(best)):
                return False
            return max(w[2].get(best, -1), w[2].get(rel(best), -1)) - max(w[2].get(cur, -1), w[2].get(rel(cur), -1)) >= margin
        ok = len(run) == confirm and all(top_ok(w) for w in run)
        if ok:
            changes.append({"time": round(t0, 3), "bar": b0 + 1, "tonic": best[0], "mode": best[1], "score": round(sc[best], 3)})
            cur = best
            i += confirm
        else:
            i += 1
    return changes


def bar_features(chords: list[dict], bar_t: list[tuple[float, float]], energy_per_bar: np.ndarray | None = None) -> np.ndarray:
    """เวกเตอร์ต่อห้อง: โครงคอร์ด (12 pitch class ถ่วงด้วยเวลา + 12 root) + พลังงาน (ถ้ามี) — ใช้คำนวณความคล้ายระหว่างห้อง"""
    from .chords import QUALITY
    F = np.zeros((len(bar_t), 24))
    for i, (t0, t1) in enumerate(bar_t):
        for c in chords:
            if c.get("root") is None:
                continue
            ov = min(t1, c["end"]) - max(t0, c["start"])
            if ov <= 0:
                continue
            for x in QUALITY[c["quality"]][1]:
                F[i, (c["root"] + x) % 12] += ov
            F[i, 12 + c["root"]] += ov * 1.5
        s = F[i].sum()
        if s > 0:
            F[i] /= s
    if energy_per_bar is not None and len(energy_per_bar) == len(bar_t):
        e = np.asarray(energy_per_bar, dtype=float)
        e = (e - e.min()) / (np.ptp(e) + 1e-9)
        F = np.hstack([F, 0.5 * e[:, None]])
    return F


def _novelty(S: np.ndarray, L: int) -> np.ndarray:
    n = S.shape[0]
    nov = np.zeros(n)
    for i in range(L, n - L + 1):
        a = S[i - L:i, i - L:i].mean() + S[i:i + L, i:i + L].mean()
        b = S[i - L:i, i:i + L].mean() + S[i:i + L, i - L:i].mean()
        nov[i] = a - b                                           # ภายในท่อนคล้ายกัน แต่ข้ามขอบท่อนต่างกัน → ค่าสูง
    return nov


def segment_structure(F: np.ndarray, energy: np.ndarray | None = None, min_bars: int = 8, L: int = 8,
                      sensitivity: float = 0.75) -> list[dict]:
    """แบ่งท่อนจากเวกเตอร์ต่อห้อง คืน [{'start_bar','end_bar'(ไม่รวม), 'label'}] (ห้องนับจาก 1)"""
    n = F.shape[0]
    if n < min_bars * 2:
        return [{"start_bar": 1, "end_bar": n + 1, "label": "A", "auto": True}]
    X = F - F.mean(axis=0)
    norm = np.linalg.norm(X, axis=1, keepdims=True)
    S = (X / np.maximum(norm, 1e-9)) @ (X / np.maximum(norm, 1e-9)).T
    nov = _novelty(S, min(L, n // 4))
    thr = nov.mean() + sensitivity * nov.std()          # สูง = ขอบท่อนน้อยลง (กันแบ่งถี่เกินในเพลงจริง)
    cands = [i for i in range(1, n) if nov[i] >= thr and nov[i] >= nov[max(0, i - 1)] and nov[i] >= nov[min(n - 1, i + 1)]]
    bounds = [0]
    for i in sorted(cands, key=lambda i: -nov[i]):               # เลือกจุดแรงสุดก่อน เว้นระยะอย่างน้อย min_bars
        if all(abs(i - b) >= min_bars for b in bounds) and n - i >= min_bars:
            bounds.append(i)
    bounds = sorted(bounds) + [n]
    segs = [(bounds[k], bounds[k + 1]) for k in range(len(bounds) - 1)]

    # จัดกลุ่มท่อนที่หน้าตาคล้ายกัน (cosine ของเวกเตอร์เฉลี่ย) → ตัวอักษร A B C ตามลำดับที่เจอ
    def cluster_segments(segs):
        means = [F[a:b].mean(axis=0) for a, b in segs]
        cl, reps = [-1] * len(segs), []
        for i, m in enumerate(means):
            for c, r in enumerate(reps):
                if float(m @ r / (np.linalg.norm(m) * np.linalg.norm(r) + 1e-9)) >= 0.9:
                    cl[i] = c
                    break
            else:
                reps.append(m)
                cl[i] = len(reps) - 1
        return cl

    cluster = cluster_segments(segs)
    merged = True
    while merged and len(segs) > 1:                              # ท่อนติดกันที่หน้าตาเหมือนกัน = ท่อนเดียวกัน (กันแบ่งถี่เกิน)
        merged = False
        for i in range(len(segs) - 1):
            if cluster[i] == cluster[i + 1]:
                segs = segs[:i] + [(segs[i][0], segs[i + 1][1])] + segs[i + 2:]
                cluster = cluster_segments(segs)
                merged = True
                break
    en = [float(np.mean(energy[a:b])) if energy is not None else 0.0 for a, b in segs]
    count = {c: cluster.count(c) for c in set(cluster)}

    # Intro/Outro ตั้งเป็นรายท่อน (ตำแหน่งแรก/สุดท้าย + พลังงานต่ำกว่ามัธยฐาน) ไม่ผูกกับกลุ่ม — Outro ที่หน้าตาซ้ำ Intro พบได้บ่อย
    override: dict[int, str] = {}
    if energy is not None and len(segs) >= 3:
        med = float(np.median(energy))
        pair_ok = cluster[0] == cluster[-1] and count[cluster[0]] == 2        # Intro กับ Outro เป็นกลุ่มเดียวกัน (มีแค่สองท่อนนี้)
        if en[0] < 0.85 * med and (count[cluster[0]] == 1 or pair_ok):
            override[0] = "Intro"
        if en[-1] <= med and (count[cluster[-1]] == 1 or pair_ok):
            override[len(segs) - 1] = "Outro"

    rest = {c: [i for i in range(len(segs)) if cluster[i] == c and i not in override] for c in set(cluster)}
    names = {c: chr(ord("A") + c) for c in set(cluster)}
    rep_clusters = [c for c in rest if len(rest[c]) >= 2]
    if energy is not None and rep_clusters:
        chorus = max(rep_clusters, key=lambda c: np.mean([en[i] for i in rest[c]]))     # ท่อนที่ซ้ำและพลังงานสูงสุด
        for c in rep_clusters:
            names[c] = "Chorus" if c == chorus else "Verse"
    total: dict[str, int] = {}
    for i, c in enumerate(cluster):
        if i not in override:
            total[names[c]] = total.get(names[c], 0) + 1
    seen: dict[str, int] = {}
    out = []
    for i, ((a, b), c) in enumerate(zip(segs, cluster)):
        if i in override:
            label = override[i]
        else:
            base = names[c]
            seen[base] = seen.get(base, 0) + 1
            label = f"{base} {seen[base]}" if total[base] > 1 else base          # เลขต่อชื่อ ไม่ซ้ำกันแม้คนละกลุ่ม
        out.append({"start_bar": a + 1, "end_bar": b + 1, "label": label, "auto": True})
    return out
