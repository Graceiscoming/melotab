"""Auto Guitar Tab Engine (plan หัวข้อ 10): เลือกตำแหน่ง (สาย, ช่อง) ของโน้ตทั้งเพลงให้ "เล่นง่ายที่สุดแต่โน้ตถูก"

แนวคิด: โน้ตหนึ่งตัวเล่นได้หลายตำแหน่ง → หาลำดับตำแหน่งที่ต้นทุนรวมต่ำสุดด้วย Viterbi (DP) เหมือนหาเส้นทางสั้นสุด
state ของ DP = (ตำแหน่งที่เลือก, anchor ของมือ): นิ้วเอื้อมได้ 4 ช่อง (anchor..anchor+3) โดยไม่ต้องย้ายมือ ยืดได้ +1/−1 พร้อมค่าปรับ
ย้ายมือเสียต้นทุนตามระยะ × ความเร็ว (โน้ตถี่ = แพง) ทำให้ "อยู่ตำแหน่งเดียวแล้วข้ามสาย" ถูกกว่า "ไถไปตามสายเดียว"
ต้นทุนอื่น: ช่องสูง สายเปล่า โทนเสียง นอก block, กระโดดข้ามสาย, legato บนสายเดียวกัน, สลับ block กลางวลี

ข้อจำกัดที่ตั้งใจ (ต้องรู้):
- น้ำหนักต้นทุนเป็นค่า heuristic ที่ตั้งเอง ยังไม่ได้ปรับกับนักกีตาร์จริง — ใช้ปุ่มทางเลือก/แก้มือได้เสมอ
- โมเดลมือแบบง่าย (anchor เดียว) ไม่แยกนิ้ว 1–4 และยังไม่ใส่ finger ให้
- ยังไม่ใส่เทคนิค (slide/bend/hammer) — เป็นงานของขั้น technique pass (Phase 5)
- ค่าความยาก/คะแนน 1–10 เป็นดัชนีเชิง heuristic ไม่ใช่มาตรฐาน
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numba import njit

from .theory import MAX_FRET_DEFAULT, TUNINGS, pitch_at, positions_for

# ดัชนีน้ำหนัก
W_SHIFT, W_PRESS, W_SKIP, W_STRETCH, W_LEGATO, W_HEIGHT, W_OPEN, W_TIMBRE, W_BLOCKSW, W_OUTBLOCK = range(10)

PRESETS: dict[str, list[float]] = {
    #            shift press skip stretch legato height open   timbre blocksw outblock
    "balanced":  [1.0, 0.15, 0.6, 2.0, 0.3, 0.5, 0.0, 0.0, 1.5, 4.0],
    "vocal_like": [1.0, 0.15, 0.6, 2.0, 0.9, 0.5, 0.6, 0.0, 1.5, 4.0],    # ชอบอยู่สายเดียวกัน (slide/legato ได้) ไม่ชอบสายเปล่า (vibrato ไม่ได้)
    "easy":      [1.6, 0.20, 0.8, 3.0, 0.2, 0.7, -0.4, 0.0, 2.0, 4.0],    # ย้ายมือน้อยสุด ชอบสายเปล่า
    "bright":    [1.0, 0.15, 0.6, 2.0, 0.3, 0.3, 0.0, 0.25, 1.5, 4.0],    # ชอบสายบาง (ช่องสูง)
    "warm":      [1.0, 0.15, 0.6, 2.0, 0.3, 0.5, 0.0, -0.25, 1.5, 4.0],   # ชอบสายหนา (ช่องต่ำ)
}
HARD_SHIFT_FRETS_PER_S = 16.0     # ย้ายมือเร็วกว่านี้ (และ ≥ 3 ช่อง) ถือว่า "เปลี่ยนตำแหน่งไม่ทัน"
K_MAX = 6


@dataclass
class TabSettings:
    transpose: int = 0
    capo: int = 0
    tuning: str = "standard"
    max_fret: int = MAX_FRET_DEFAULT
    blocks: list[dict] = field(default_factory=list)       # block ที่เลือก (ว่าง = ไม่จำกัด)
    block_mode: str = "multi"                              # "single" ใช้เฉพาะ block แรก | "multi" ย้ายระหว่าง block ได้
    out_of_block: str = "octave_shift"                     # "octave_shift" | "stretch" | "warn"
    preset: str = "balanced"
    weights: list[float] | None = None                     # override ทั้งชุด (ถ้าไม่ใส่ใช้ตาม preset)

    @classmethod
    def from_dict(cls, d: dict) -> "TabSettings":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def w(self) -> np.ndarray:
        return np.array(self.weights if self.weights is not None else PRESETS.get(self.preset, PRESETS["balanced"]), dtype=np.float64)

    def tuning_midi(self) -> list[int]:
        return TUNINGS[self.tuning]


# ---------------------------------------------------------------- ต้นทุน (Numba)

ANCHOR_MAX = 20
INF = 1e18


@njit(cache=True)
def _unary(s, f, blk_out, w):
    c = w[W_HEIGHT] * max(0, f - 12) / 10.0
    if f == 0:
        c += w[W_OPEN]
    c += w[W_TIMBRE] * (s - 1) / 5.0                       # s ใหญ่ = สายหนา; timbre บวก = ชอบสายบาง
    if blk_out:
        c += w[W_OUTBLOCK]
    return c


@njit(cache=True)
def _step(sa, fa, ba, aa, sb, fb, bb, ab, dt, w):
    """ต้นทุนเปลี่ยนจากโน้ตก่อนหน้า (สาย sa ช่อง fa block ba anchor aa) ไปโน้ตนี้ (sb fb bb ab); คืน INF ถ้าเป็นไปไม่ได้"""
    c = 0.0
    ds = abs(sb - sa)
    if ds > 1:
        c += w[W_SKIP] * (ds - 1)
    if ba != bb:
        c += w[W_BLOCKSW] * (1.0 if dt < 0.5 else 0.2)     # สลับ block กลางวลีแพงกว่าตอนพัก
    if sa == sb and fa > 0 and fb > 0 and 0 < abs(fb - fa) <= 2:
        c -= w[W_LEGATO]                                   # สายเดียวกันขยับใกล้ ๆ = ทำ slide/hammer/pull ได้
    if fb == 0:                                            # สายเปล่า: มือไม่ต้องอยู่ตรงไหน
        return c if ab == aa else INF
    if ab == aa:                                           # ไม่ย้ายมือ: ต้องเอื้อมถึง
        if aa <= fb <= aa + 3:
            return c
        if fb == aa + 4 or fb == aa - 1:
            return c + w[W_STRETCH] * 0.5
        return INF
    if not (ab <= fb <= ab + 3):                           # ย้ายมือไป anchor ใหม่ ต้องครอบช่องของโน้ตนี้
        return INF
    pressure = 1.0 + w[W_PRESS] / max(dt, 0.05)            # โน้ตถี่ = ย้ายตำแหน่งแพงขึ้น
    relax = 1.0
    if dt > 2.0:
        relax = 0.1                                        # พักยาว ย้ายมือได้สบาย
    elif dt > 0.8:
        relax = 0.3
    if fa == 0:
        relax *= 0.4                                       # โน้ตก่อนหน้าเป็นสายเปล่า = มีเวลาขยับมือ
    return c + w[W_SHIFT] * abs(ab - aa) * pressure * relax


@njit(cache=True)
def _viterbi(S, F, B, O, valid, t, w):
    n, K = S.shape
    A = ANCHOR_MAX + 1
    dp = np.full((n, K, A), INF)
    bj = np.full((n, K, A), -1, np.int64)
    ba_ = np.full((n, K, A), -1, np.int64)
    for k in range(K):
        if not valid[0, k]:
            continue
        u = _unary(S[0, k], F[0, k], O[0, k], w)
        f = F[0, k]
        if f == 0:
            for a in range(1, A):
                dp[0, k, a] = u
        else:
            for a in range(max(1, f - 3), min(f, ANCHOR_MAX) + 1):
                dp[0, k, a] = u
    for i in range(1, n):
        dt = t[i] - t[i - 1]
        for k in range(K):
            if not valid[i, k]:
                continue
            f = F[i, k]
            u = _unary(S[i, k], f, O[i, k], w)
            for j in range(K):
                if not valid[i - 1, j]:
                    continue
                for ap in range(1, A):
                    base = dp[i - 1, j, ap]
                    if base >= INF:
                        continue
                    # 1) ไม่ย้ายมือ (anchor เดิม)
                    c = _step(S[i - 1, j], F[i - 1, j], B[i - 1, j], ap, S[i, k], f, B[i, k], ap, dt, w)
                    if c < INF and base + c + u < dp[i, k, ap]:
                        dp[i, k, ap] = base + c + u
                        bj[i, k, ap] = j
                        ba_[i, k, ap] = ap
                    # 2) ย้ายไป anchor ใหม่ที่ครอบช่องนี้
                    if f > 0:
                        for a in range(max(1, f - 3), min(f, ANCHOR_MAX) + 1):
                            if a == ap:
                                continue
                            c = _step(S[i - 1, j], F[i - 1, j], B[i - 1, j], ap, S[i, k], f, B[i, k], a, dt, w)
                            if c < INF and base + c + u < dp[i, k, a]:
                                dp[i, k, a] = base + c + u
                                bj[i, k, a] = j
                                ba_[i, k, a] = ap
    bestv = INF
    bk = 0
    bA = 1
    for k in range(K):
        for a in range(1, A):
            if valid[n - 1, k] and dp[n - 1, k, a] < bestv:
                bestv = dp[n - 1, k, a]
                bk = k
                bA = a
    pk = np.full(n, -1, np.int64)
    pa = np.full(n, -1, np.int64)
    pk[n - 1] = bk
    pa[n - 1] = bA
    for i in range(n - 1, 0, -1):
        j = bj[i, pk[i], pa[i]]
        ap = ba_[i, pk[i], pa[i]]
        pk[i - 1] = j
        pa[i - 1] = ap
    return pk, pa, bestv


# ---------------------------------------------------------------- สร้าง candidate

def _block_of(fret: int, blocks: list[dict]) -> int:
    for i, b in enumerate(blocks):
        if b["fret_min"] <= fret <= b["fret_max"]:
            return i
    return -1


def _candidates(pitch: int, st: TabSettings, tuning: list[int]) -> tuple[list[tuple[int, int, int, bool]], dict]:
    """คืน ([(string, fret, block_idx, out_of_block)], flags) ตาม Block Mode และนโยบายนอก block"""
    flags: dict = {}
    allpos = positions_for(pitch, tuning, st.capo, st.max_fret)
    blocks = st.blocks[:1] if (st.block_mode == "single" and st.blocks) else st.blocks
    if not blocks:
        return [(s, f, 0, False) for s, f in allpos], flags
    inb = [(s, f, _block_of(f, blocks), False) for s, f in allpos if _block_of(f, blocks) >= 0]
    if inb:
        return inb, flags
    # ไม่มีตำแหน่งใน block เลย → ตามนโยบายที่ผู้ใช้เลือก (และแจ้งธงชัดเจนทุกครั้ง)
    if st.out_of_block == "octave_shift":
        for shift in (12, -12, 24, -24):
            alt = [(s, f, _block_of(f, blocks), False) for s, f in positions_for(pitch + shift, tuning, st.capo, st.max_fret)
                   if _block_of(f, blocks) >= 0]
            if alt:
                flags["octave_shifted"] = shift
                return alt, flags
    elif st.out_of_block == "stretch":
        for pad in (1, 2, 3):
            alt = [(s, f, 0, False) for s, f in allpos
                   if any(b["fret_min"] - pad <= f <= b["fret_max"] + pad for b in blocks)]
            if alt:
                flags["out_of_block"] = True
                return alt, flags
    if allpos:                                              # "warn" หรือทางสุดท้าย: ยอมออกนอก block พร้อมค่าปรับ
        flags["out_of_block"] = True
        return [(s, f, 0, True) for s, f in allpos], flags
    return [], flags


# ---------------------------------------------------------------- generate

def generate_tab(notes: list[dict], settings: TabSettings | dict | None = None, locked: dict[str, dict] | None = None) -> dict:
    st = settings if isinstance(settings, TabSettings) else TabSettings.from_dict(settings or {})
    tuning = st.tuning_midi()
    locked = locked or {}
    w = st.w()

    items = sorted(notes, key=lambda n: (n["start"], n["midi"]))
    seq: list[dict] = []             # โน้ตที่เล่นได้ (เข้า DP)
    events: dict[str, dict] = {}
    for n in items:
        pitch = n["midi"] + st.transpose
        cands, flags = _candidates(pitch, st, tuning)
        lk = locked.get(n["id"])
        lock_ok = bool(lk and pitch_at(lk["string"], lk["fret"], tuning, st.capo) == pitch and 0 <= lk["fret"] <= st.max_fret)
        if lock_ok:
            cands = [(lk["string"], lk["fret"], max(_block_of(lk["fret"], st.blocks), 0) if st.blocks else 0, False)]
            flags = {}
        ev = {"id": f"t_{n['id']}", "note_id": n["id"], "pitch": pitch, "string": None, "fret": None,
              "start": n["start"], "end": n["end"],
              "start_beat": n.get("start_beat_q", n.get("start_beat")), "dur_beats": n.get("dur_beats_q", n.get("dur_beats")),
              "techniques": {}, "bend": None, "finger": None, "locked": lock_ok,
              "difficulty": 0.0, "warnings": [], **flags}
        if not cands:
            ev["warnings"].append("unplayable")             # นอกช่วงเสียงของกีตาร์ (หรือ capo สูงเกิน)
            ev["locked"] = False
            events[n["id"]] = ev
            continue
        if flags.get("octave_shifted"):
            ev["pitch"] = pitch + flags["octave_shifted"]
            ev["warnings"].append("octave_shifted")
        if flags.get("out_of_block"):
            ev["warnings"].append("out_of_block")
        events[n["id"]] = ev
        seq.append({"note": n, "cands": cands[:K_MAX], "ev": ev})

    summary = {"notes": len(items), "playable": len(seq), "total_cost": 0.0}
    if seq:
        n = len(seq)
        S = np.zeros((n, K_MAX), np.int64)
        F = np.zeros((n, K_MAX), np.int64)
        B = np.zeros((n, K_MAX), np.int64)
        O = np.zeros((n, K_MAX), np.bool_)
        V = np.zeros((n, K_MAX), np.bool_)
        for i, it in enumerate(seq):
            for k, (s, f, b, o) in enumerate(it["cands"]):
                S[i, k], F[i, k], B[i, k], O[i, k], V[i, k] = s, f, max(b, 0), o, True
        t = np.array([it["note"]["start"] for it in seq])
        pk, pa, total = _viterbi(S, F, B, O, V, t, w)
        summary["total_cost"] = round(float(total), 2)
        for i, it in enumerate(seq):
            k, a = int(pk[i]), int(pa[i])
            s, f = int(S[i, k]), int(F[i, k])
            ev = it["ev"]
            ev["string"], ev["fret"], ev["anchor"] = s, f, a
            local = float(_unary(s, f, bool(O[i, k]), w))
            if i > 0:
                pj, pap = int(pk[i - 1]), int(pa[i - 1])
                dt = float(t[i] - t[i - 1])
                local += float(_step(S[i - 1, pj], F[i - 1, pj], B[i - 1, pj], pap, s, f, B[i, k], a, dt, w))
                move = abs(a - pap)
                if f > 0 and move >= 3 and move / max(dt, 0.02) > HARD_SHIFT_FRETS_PER_S:
                    ev["warnings"].append("hard_shift")                 # ย้ายมือไกลในเวลาสั้น = เปลี่ยนตำแหน่งไม่ทัน
                if f > 0 and (f == a + 4 or f == a - 1) and dt < 0.6:
                    ev["warnings"].append("stretch")                    # ต้องยืดนิ้วในโน้ตถี่
            ev["difficulty"] = round(float(np.clip(local / 6.0, 0.0, 1.0)), 3)
            if any(x in ev["warnings"] for x in ("hard_shift", "stretch")):
                ev["difficulty"] = max(ev["difficulty"], 0.85)

    ordered = [events[n["id"]] for n in items]
    summary.update(difficulty=difficulty_score(ordered),
                   hard=sum(1 for e in ordered if "hard_shift" in e["warnings"] or "stretch" in e["warnings"]),
                   unplayable=sum(1 for e in ordered if "unplayable" in e["warnings"]),
                   out_of_block=sum(1 for e in ordered if "out_of_block" in e["warnings"]),
                   octave_shifted=sum(1 for e in ordered if "octave_shifted" in e["warnings"]))
    return {"settings": _settings_dict(st), "events": ordered, "summary": summary}


def difficulty_score(events: list[dict]) -> float:
    """ดัชนีความยาก 1–10 (heuristic): ผสมค่าเฉลี่ยความยากต่อโน้ตกับสัดส่วนจุดที่ "เล่นไม่ทัน/ยืดเกิน" """
    ev = [e for e in events if e.get("fret") is not None]
    if not ev:
        return 1.0
    mean = float(np.mean([e["difficulty"] for e in ev]))
    hard = sum(1 for e in ev if "hard_shift" in e["warnings"] or "stretch" in e["warnings"]) / len(ev)
    return round(1 + 9 * float(np.clip(0.6 * mean * 1.5 + 0.4 * min(1.0, hard * 5), 0, 1)), 1)


def _settings_dict(st: TabSettings) -> dict:
    return {"transpose": st.transpose, "capo": st.capo, "tuning": st.tuning, "max_fret": st.max_fret,
            "blocks": st.blocks, "block_mode": st.block_mode, "out_of_block": st.out_of_block, "preset": st.preset}


# ---------------------------------------------------------------- ทางเลือก

def alternatives(notes: list[dict], settings: TabSettings | dict, locked: dict[str, dict] | None, note_id: str, top: int = 3) -> list[dict]:
    """ตำแหน่งทางเลือกของโน้ต note_id: ตรึงตำแหน่งนั้นแล้วรัน DP ทั้งเพลงใหม่ (ตัวอื่นปรับตามอัตโนมัติ)
    คืน [{string, fret, delta_cost, hard}] เรียงจากดีสุด (delta_cost = ต้นทุนรวมที่เพิ่มจากคำตอบของระบบ)"""
    st = settings if isinstance(settings, TabSettings) else TabSettings.from_dict(settings)
    locked = {k: v for k, v in (locked or {}).items() if k != note_id}
    base = generate_tab(notes, st, locked)
    cur = next((e for e in base["events"] if e["note_id"] == note_id), None)
    if not cur or cur["fret"] is None:
        return []
    cands, _ = _candidates(cur["pitch"], TabSettings(**{**_settings_dict(st), "out_of_block": "warn"}), st.tuning_midi())
    out = []
    for s, f, *_ in cands:
        if (s, f) == (cur["string"], cur["fret"]):
            continue
        r = generate_tab(notes, st, {**locked, note_id: {"string": s, "fret": f}})
        out.append({"string": s, "fret": f, "pitch": cur["pitch"],
                    "delta_cost": round(r["summary"]["total_cost"] - base["summary"]["total_cost"], 2),
                    "hard": r["summary"]["hard"] - base["summary"]["hard"]})
    return sorted(out, key=lambda a: (a["delta_cost"], a["hard"]))[:top]
