"""โมเดลกลางสำหรับ export: รวม song + tab + เทคนิค เป็นห้อง (measure) ที่ quantize เป็น 16 ส่วน — ทุก writer ใช้ตัวนี้ร่วมกัน

ข้อตกลง/ข้อจำกัด (ต้องรู้):
- 1 beat ใน beat grid = โน้ตตัวดำ (quarter) เสมอ; ห้องที่ beat grid ยาวไม่เท่ากัน (pickup/จังหวะเปลี่ยน) ได้ time signature ต่อห้องเป็น n/4
- เมโลดี้เป็นเสียงเดียว: ความยาวโน้ต = min(ความยาวจริง, ถึงโน้ตถัดไป, ถึงปลายห้อง) แล้วปัดลงเป็นค่ามาตรฐาน (1,2,3,4,6,8,12,16 ส่วน 16) ที่เหลือเป็นพัก — ไม่มี tie ข้ามห้อง
- เทคนิคมาจาก tab.json (`techniques[note_id]`) ที่ผู้ใช้/ระบบใส่ไว้
"""
from __future__ import annotations

from ..pipeline.structure import bars_from_beats

DURS = (16, 12, 8, 6, 4, 3, 2, 1)         # ความยาวมาตรฐานเป็น 16 ส่วนของตัวดำ×4 (16 = ตัวกลม)
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def time_to_beat(beats: list[dict], t: float) -> float:
    """เวลา (s) → ตำแหน่ง beat (ทศนิยม) บน beat grid"""
    if not beats:
        return t * 2.0
    if t <= beats[0]["time"]:
        return 0.0
    for i in range(len(beats) - 1):
        a, b = beats[i]["time"], beats[i + 1]["time"]
        if a <= t < b:
            return i + (t - a) / max(b - a, 1e-6)
    return len(beats) - 1 + (t - beats[-1]["time"]) / max(beats[-1]["time"] - beats[-2]["time"], 1e-6) if len(beats) > 1 else 0.0


def beat_to_time(beats: list[dict], beat: float) -> float:
    if not beats:
        return beat / 2.0
    i = int(max(0, min(beat, len(beats) - 1)))
    if i >= len(beats) - 1:
        step = (beats[-1]["time"] - beats[-2]["time"]) if len(beats) > 1 else 0.5
        return beats[-1]["time"] + (beat - (len(beats) - 1)) * step
    return beats[i]["time"] + (beat - i) * (beats[i + 1]["time"] - beats[i]["time"])


def split_rest(n16: int) -> list[int]:
    out = []
    while n16 > 0:
        d = next(x for x in DURS if x <= n16)
        out.append(d)
        n16 -= d
    return out


def build(song: dict, tab: dict | None, title: str = "") -> dict:
    """คืน {title, key, bpm, capo, tuning(midi สาย 6→1), transpose, measures:[{index,start_beat,beats,items:[...]}], sections, chords, lyrics, bars}"""
    beats = song.get("beats") or []
    bars = bars_from_beats(beats) if beats else []
    total_beats = len(beats)
    if not bars:                                                    # ไม่มี beat grid: 4/4 สังเคราะห์
        last = max((n.get("start_beat_q", n.get("start_beat", 0)) or 0 for n in song.get("notes", [])), default=0)
        bars = [(s, 4) for s in range(0, int(last) + 5, 4)]
        total_beats = bars[-1][0] + 4
    settings = (tab or {}).get("settings") or {}
    techniques = (tab or {}).get("techniques") or {}
    from ..tab.theory import TUNINGS
    tuning = TUNINGS.get(settings.get("tuning", "standard"), TUNINGS["standard"])

    evs = []
    for e in sorted((tab or {}).get("events", []), key=lambda x: x["start"]):
        if e.get("string") is None or e.get("fret") is None:
            continue
        sb = e.get("start_beat")
        if sb is None:
            sb = time_to_beat(beats, e["start"])
        db = e.get("dur_beats") or max(0.25, time_to_beat(beats, e["end"]) - time_to_beat(beats, e["start"]))
        tq = techniques.get(e["note_id"], {})
        evs.append({**e, "beat": float(sb), "dur": float(db), "tech": tq})

    measures = []
    k = 0
    for bi, (s, n) in enumerate(bars):
        L = n * 4
        items = []
        while k < len(evs) and evs[k]["beat"] < s + n - 1e-6:
            e = evs[k]
            if e["beat"] < s - 1e-6:                                  # ก่อนห้องแรก (ไม่ควรเกิด) ปัดเข้าห้องแรก
                e["beat"] = s
            st = min(L - 1, max(0, round((e["beat"] - s) * 4)))
            items.append({"start16": st, "event": e})
            k += 1
        # ความยาว
        out = []
        cursor = 0
        for j, it in enumerate(items):
            if it["start16"] < cursor:                                # โน้ตซ้อนกันหลัง quantize: เลื่อนต่อท้ายโน้ตก่อนหน้า (ไม่ทิ้งโน้ต)
                it["start16"] = cursor
            if it["start16"] >= L:
                it["start16"] = L - 1
            if it["start16"] > cursor:
                out += [{"start16": cursor + sum(split_rest(it["start16"] - cursor)[:i]), "dur16": d, "event": None}
                        for i, d in enumerate(split_rest(it["start16"] - cursor))]
            nxt = items[j + 1]["start16"] if j + 1 < len(items) else L
            nxt = max(nxt, it["start16"] + 1)
            want = min(max(1, round(it["event"]["dur"] * 4)), nxt - it["start16"], L - it["start16"])
            d = next(x for x in DURS if x <= want)
            out.append({"start16": it["start16"], "dur16": d, "event": it["event"]})
            cursor = it["start16"] + d
            if j + 1 < len(items) and items[j + 1]["start16"] < cursor:
                items[j + 1]["start16"] = cursor
        if cursor < L:
            pos = cursor
            for d in split_rest(L - cursor):
                out.append({"start16": pos, "dur16": d, "event": None})
                pos += d
        measures.append({"index": bi, "start_beat": s, "beats": n, "items": out})
    # โน้ตที่เหลือเกินห้องสุดท้าย (ไม่ควรเกิดเพราะห้องสุดท้ายขยายตามจำนวน beat) — ไม่ทำอะไร

    key = song.get("key")
    return {
        "title": title or song.get("source", {}).get("title", "") or "",
        "key": f"{key['tonic']} {'minor' if key['mode'] == 'minor' else 'major'}" if key else "",
        "bpm": (song.get("tempo") or {}).get("bpm") or 120.0,
        "capo": int(settings.get("capo", 0)), "transpose": int(settings.get("transpose", 0)),
        "tuning_name": settings.get("tuning", "standard"), "tuning": tuning,
        "time_signature": song.get("time_signature") or {"num": 4, "den": 4},
        "measures": measures, "bars": bars, "beats": beats, "total_beats": total_beats,
        "sections": song.get("sections") or [], "chords": song.get("chords") or [],
        "lyrics": song.get("lyrics"), "notes": song.get("notes") or [], "events": evs,
    }


def section_bar_range(model: dict, sec: dict) -> tuple[int, int]:
    """ท่อน → (ห้องแรก, ห้องสุดท้าย+1) ตามดัชนีห้องของ model (0-based)"""
    starts = [m["start_beat"] for m in model["measures"]]
    t0 = sec.get("start")
    beat0 = time_to_beat(model["beats"], t0) if (t0 is not None and model["beats"]) else None
    t1 = sec.get("end")
    beat1 = time_to_beat(model["beats"], t1) if (t1 is not None and model["beats"]) else None
    if beat0 is None:
        a = max(0, sec.get("start_bar", 1) - 1)
        b = max(a + 1, sec.get("end_bar", a + 2) - 1)
        return a, min(b, len(starts))
    a = max((i for i, s in enumerate(starts) if s <= beat0 + 0.5), default=0)
    b = next((i for i, s in enumerate(starts) if s >= (beat1 - 0.5 if beat1 is not None else 1e9)), len(starts))
    return a, max(a + 1, b)


def chord_at_beat(chords: list[dict], beat: float) -> dict | None:
    for c in chords:
        if c["start_beat"] <= beat + 1e-6 < c["end_beat"]:
            return c
    return None


def tech_marks(t: dict) -> str:
    m = ""
    if t.get("in") == "slide_in":
        m += "/"
    on = t.get("on") or []
    if "bend" in on:
        m += "b"
    if "release" in on:
        m += "r"
    if "vibrato" in on:
        m += "~"
    m += {"hammer": "h", "pull": "p", "slide": "/"}.get(t.get("to_next"), "")
    return m
