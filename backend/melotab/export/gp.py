"""Export Guitar Pro 5 (.gp5) ด้วย pyguitarpro — เปิดได้ใน Guitar Pro / TuxGuitar / MuseScore

หมายเหตุ: เขียนเป็น GP5 (ฟอร์แมตเก่าที่ทุกโปรแกรมอ่านได้) ไม่ใช่ .gp (GPX/GP8) ที่เป็นฟอร์แมตปิด
ข้อความ (ชื่อเพลง/ชื่อท่อน) ใช้ cp874 รองรับไทย; ยังไม่ได้ทดสอบเปิดด้วย Guitar Pro จริง (ไม่มีโปรแกรมในเครื่อง) ตรวจแค่เขียน→อ่านกลับด้วยไลบรารีเดียวกัน
"""
from __future__ import annotations

from pathlib import Path

import guitarpro as gp

TICKS = 960                                                  # ticks ต่อตัวดำใน GP
DUR = {16: (1, False), 12: (2, True), 8: (2, False), 6: (4, True), 4: (4, False), 3: (8, True), 2: (8, False), 1: (16, False)}
BEND_UNIT = 25                                               # GP: 1 semitone = 25 หน่วย


def write_gp5(model: dict, path: Path) -> dict:
    song = gp.Song()
    song.title = model["title"] or "MeloTab"
    song.artist = ""
    song.tempo = int(round(model["bpm"]))
    song.measureHeaders.clear()
    song.tracks.clear()
    start = TICKS
    sec_by_bar = {}
    for s in model["sections"]:
        sec_by_bar[max(0, (s.get("start_bar") or 1) - 1)] = s.get("label") or "Section"
    for m in model["measures"]:
        h = gp.MeasureHeader(number=m["index"] + 1, start=start)
        h.timeSignature = gp.TimeSignature(numerator=m["beats"], denominator=gp.Duration(value=4))
        if m["index"] in sec_by_bar:
            h.marker = gp.Marker(title=str(sec_by_bar[m["index"]]))
        song.measureHeaders.append(h)
        start += m["beats"] * TICKS
    tr = gp.Track(song, number=1, name="Guitar", offset=model["capo"])
    tr.strings = [gp.GuitarString(i + 1, midi) for i, midi in enumerate(reversed(model["tuning"]))]    # สาย 1 = สูงสุด
    tr.channel.instrument = 29                                                                         # overdriven guitar
    tr.measures.clear()
    song.tracks.append(tr)

    flat = [it["event"] for m in model["measures"] for it in m["items"] if it["event"] is not None]
    nxt_of = {id(a): b for a, b in zip(flat, flat[1:])}
    n_notes = 0
    for m, h in zip(model["measures"], song.measureHeaders):
        ms = gp.Measure(tr, h)
        tr.measures.append(ms)
        voice = ms.voices[0]
        voice.beats.clear()
        for it in m["items"]:
            val, dotted = DUR[it["dur16"]]
            b = gp.Beat(voice, duration=gp.Duration(value=val, isDotted=dotted))
            b.start = h.start + it["start16"] * (TICKS // 4)
            e = it["event"]
            if e is None:
                b.status = gp.BeatStatus.rest
            else:
                b.status = gp.BeatStatus.normal
                n = gp.Note(b, value=int(e["fret"]), string=int(e["string"]), type=gp.NoteType.normal)
                t = e["tech"]
                on = t.get("on") or []
                nxt = t.get("to_next")
                if nxt == "hammer" or nxt == "pull":
                    n.effect.hammer = True                              # GP ใช้ธง hammer เดียวสำหรับทั้ง hammer-on/pull-off
                if nxt == "slide" and id(e) in nxt_of:
                    n.effect.slides = [gp.SlideType.shiftSlideTo]
                if t.get("in") == "slide_in":
                    n.effect.slides = [gp.SlideType.intoFromBelow]
                if "vibrato" in on:
                    n.effect.vibrato = True
                if "bend" in on:
                    v = int(t.get("bend_semitones", 1)) * BEND_UNIT
                    n.effect.bend = gp.BendEffect(type=gp.BendType.bend, value=v, points=[
                        gp.BendPoint(position=0, value=0), gp.BendPoint(position=3, value=v), gp.BendPoint(position=12, value=v)])
                b.notes.append(n)
                n_notes += 1
            voice.beats.append(b)
    path.parent.mkdir(parents=True, exist_ok=True)
    # GP5 เก็บข้อความเป็น code page เดียว: ใช้ cp874 (ไทย+ละติน) ถ้าชื่อมีอักษรอื่นที่ไม่รองรับให้แทนด้วย "?" แทนที่จะล้มทั้งไฟล์
    def fit(t: str) -> str:
        return t.encode("cp874", errors="replace").decode("cp874")

    song.title = fit(song.title)
    for h in song.measureHeaders:
        if h.marker:
            h.marker.title = fit(h.marker.title)
    gp.write(song, str(path), version=(5, 1, 0), encoding="cp874")
    return {"measures": len(model["measures"]), "notes": n_notes}
