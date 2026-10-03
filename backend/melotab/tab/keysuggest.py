"""แนะนำคีย์ที่เล่นง่าย + capo (plan หัวข้อ 13)

ลอง transpose −6…+6 semitone × capo 0…7 รัน Tab Engine ทุกแบบ ให้คะแนนจาก:
  ต้นทุนรวมของ fingering, จำนวนโน้ตที่เล่นไม่ได้/จุดยาก, ความเป็นมิตรของ "คีย์ของรูปมือ" (E A D G C + Em Am ฯลฯ มีสายเปล่าช่วย)
แยกเป็น 2 กลุ่มชัดเจน: เสียงเท่าต้นฉบับ (transpose = 0, ใช้ capo) กับเปลี่ยนคีย์ (เสียงต่างจากต้นฉบับ)

ข้อจำกัด: คะแนนเป็น heuristic เทียบกันเองในเพลงเดียวกัน ยังไม่ใช่ความยากสัมบูรณ์ และยังไม่รวมความง่ายของ "คอร์ด" (ยังไม่มีคอร์ดใน Phase 3)
"""
from __future__ import annotations

from .engine import TabSettings, generate_tab
from .theory import NOTE_NAMES, pc_of

# คีย์ของ "รูปมือ" ที่กีตาร์เล่นสะดวก (มีสายเปล่าช่วย) — ค่ายิ่งต่ำยิ่งดี (เป็นโบนัส/โทษต่อคะแนน)
_FRIENDLY_MAJOR = {"E": 0.0, "A": 0.0, "D": 0.0, "G": 0.0, "C": 0.2}
_FRIENDLY_MINOR = {"E": 0.0, "A": 0.0, "D": 0.1, "B": 0.4}


def shape_key_penalty(tonic: str, mode: str, transpose: int, capo: int) -> float:
    """รูปมือที่ใช้จริง = คีย์ของเพลงหลัง transpose แล้วลบ capo (capo สูงขึ้น = รูปมือเป็นคีย์ต่ำลง)"""
    pc = (pc_of(tonic) + transpose - capo) % 12
    name = NOTE_NAMES[pc]
    table = _FRIENDLY_MINOR if mode == "minor" else _FRIENDLY_MAJOR
    return table.get(name, 1.5)


def suggest(notes: list[dict], key: dict | None, base: TabSettings | dict | None = None,
            transposes: range = range(-6, 7), capos: range = range(0, 8), top: int = 12) -> dict:
    st0 = base if isinstance(base, TabSettings) else TabSettings.from_dict(base or {})
    tonic, mode = (key["tonic"], key["mode"]) if key else ("C", "major")
    rows = []
    for tr in transposes:
        for capo in capos:
            st = TabSettings(**{**st0.__dict__, "transpose": tr, "capo": capo, "blocks": []})
            r = generate_tab(notes, st)
            s = r["summary"]
            n = max(1, s["notes"])
            penalty = shape_key_penalty(tonic, mode, tr, capo)
            # โน้ตที่เล่นไม่ได้ = โน้ตหายจากแทป หนักกว่าจุดยากมาก (25 vs 6 หน่วยต้นทุนต่อจุด) เพื่อไม่ให้ capo/คีย์ที่ทำให้โน้ตหายได้อันดับต้น
            score = (s["total_cost"] + 25.0 * s["unplayable"] + 6.0 * s["hard"]) / n + 0.5 * penalty
            rows.append({
                "transpose": tr, "capo": capo,
                "kind": "same_sound" if tr == 0 else "transposed",
                "shape_key": f"{NOTE_NAMES[(pc_of(tonic) + tr - capo) % 12]}{'m' if mode == 'minor' else ''}",
                "sounding_key": f"{NOTE_NAMES[(pc_of(tonic) + tr) % 12]}{'m' if mode == 'minor' else ''}",
                "score": round(score, 3), "difficulty": s["difficulty"], "hard": s["hard"], "unplayable": s["unplayable"],
                "friendly": penalty <= 0.2,
            })
    # ตัวเลือกที่เล่นได้ครบทุกโน้ตมาก่อนเสมอ (โน้ตหายจากแทปยอมรับไม่ได้โดยไม่บอก) แล้วค่อยเรียงตามคะแนน
    rows.sort(key=lambda r: (r["unplayable"] > 0, r["score"]))
    return {"original_key": f"{tonic} {mode}",
            "same_sound": [r for r in rows if r["kind"] == "same_sound"][:top],
            "transposed": [r for r in rows if r["kind"] == "transposed"][:top],
            "best": rows[0] if rows else None}
