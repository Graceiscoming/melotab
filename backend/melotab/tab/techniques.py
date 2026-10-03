"""แปลง ornament ของเสียงร้อง → เทคนิคกีตาร์บนแทป พร้อมกติกา feasibility (plan หัวข้อ 12, 10.3) — Phase 5

รูปแบบผลลัพธ์ตรงกับที่ UI เก็บใน `techniques[note_id]`: {"in": "slide_in", "on": ["vibrato","bend"], "to_next": "hammer|pull|slide"}
คืนเป็นข้อเสนอ (techniques) + ปริมาณ bend (semitone) + รายการที่ถูกปฏิเสธพร้อมเหตุผล — ไม่ทับเทคนิคที่ผู้ใช้ใส่เอง (ฝั่ง UI เป็นคนรวม)

กติกา feasibility:
- vibrato / bend: ต้องไม่ใช่สายเปล่า (ช่อง 0)
- bend: ไม่เกิน 1.5 เสียง (3 semitone) บนสาย 1–3, ไม่เกิน 1 เสียง (2 semitone) บนสาย 4–6; ปัดทีละครึ่งเสียง
- hammer/pull: ต้องสายเดียวกัน ต่างกัน 1–4 ช่อง (hammer = ไปช่องสูงกว่า, pull = ต่ำกว่า)
- slide: สายเดียวกัน ต่างกัน ≥ 1 ช่อง และต้นทางไม่ใช่สายเปล่า; slide_in ต้องตัวโน้ตอยู่ช่อง ≥ 2
ข้อจำกัด: เกณฑ์ heuristic ยังไม่ผ่านการปรับกับนักกีตาร์จริง
"""
from __future__ import annotations

MAX_LEGATO_FRET_DIFF = 4
MAX_GAP_S = 0.15


def _bend_limit(string: int) -> int:
    return 3 if string <= 3 else 2


def suggest_techniques(events: list[dict], notes: list[dict]) -> dict:
    by_note = {n["id"]: n for n in notes}
    evs = sorted((e for e in events if e.get("fret") is not None), key=lambda e: e["start"])
    sugg: dict[str, dict] = {}
    bends: dict[str, int] = {}
    rejected: list[dict] = []

    def rej(e: dict, what: str, why: str) -> None:
        rejected.append({"note_id": e["note_id"], "technique": what, "reason": why})

    def put(e: dict) -> dict:
        return sugg.setdefault(e["note_id"], {})

    for i, e in enumerate(evs):
        orn = {o["type"]: o for o in by_note.get(e["note_id"], {}).get("ornaments", [])}
        s, f = e["string"], e["fret"]
        if "vibrato" in orn:
            if f == 0:
                rej(e, "vibrato", "สายเปล่าทำ vibrato ไม่ได้")
            else:
                put(e).setdefault("on", []).append("vibrato")
        if "bend_up" in orn:
            semis = max(0, round(orn["bend_up"]["cents"] / 100.0))
            if f == 0:
                rej(e, "bend", "สายเปล่า bend ไม่ได้")
            elif semis < 1:
                pass
            elif semis > _bend_limit(s):
                rej(e, "bend", f"bend {semis} semitone เกินที่สาย {s} ทำได้ ({_bend_limit(s)})")
            elif "vibrato" not in sugg.get(e["note_id"], {}).get("on", []):      # bend+vibrato พร้อมกันไม่ใส่อัตโนมัติ
                put(e).setdefault("on", []).append("bend")
                bends[e["note_id"]] = semis
        if "scoop_in" in orn:
            if f >= 2:
                put(e)["in"] = "slide_in"
            else:
                rej(e, "slide_in", "ช่องต่ำเกินกว่าจะสไลด์เข้า")
        tr = next((o for o in orn.values() if o["type"] in ("slide_next", "legato_next")), None)
        if tr and i + 1 < len(evs):
            nx = evs[i + 1]
            if nx["start"] - e["end"] > MAX_GAP_S:
                continue
            df = nx["fret"] - f
            same = nx["string"] == s
            if tr["type"] == "legato_next":
                if not same:
                    rej(e, "hammer/pull", "โน้ตถัดไปอยู่คนละสาย")
                elif df == 0 or abs(df) > MAX_LEGATO_FRET_DIFF:
                    rej(e, "hammer/pull", f"ช่องห่างกัน {abs(df)} (ทำได้ 1–{MAX_LEGATO_FRET_DIFF})")
                else:
                    put(e)["to_next"] = "hammer" if df > 0 else "pull"
            else:
                if not same:
                    rej(e, "slide", "โน้ตถัดไปอยู่คนละสาย")
                elif df == 0:
                    rej(e, "slide", "ไม่มีระยะให้สไลด์")
                elif f == 0:
                    rej(e, "slide", "สไลด์จากสายเปล่าไม่ได้")
                else:
                    put(e)["to_next"] = "slide"
    return {"techniques": sugg, "bends": bends, "rejected": rejected}
