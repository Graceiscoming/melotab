"""Export MusicXML (.musicxml): 1 part, 2 staff (โน้ตสากล + TAB) พร้อม chord symbol และเทคนิค hammer/pull/slide/bend/vibrato

ใช้ตัวสร้าง XML ของ stdlib; ดูข้อจำกัดเรื่อง quantize/ความยาวใน model.py
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .model import NAMES

DIV = 4                                                    # divisions ต่อตัวดำ → 1 หน่วย = 16 ส่วน
TYPE = {16: ("whole", 0), 12: ("half", 1), 8: ("half", 0), 6: ("quarter", 1), 4: ("quarter", 0), 3: ("eighth", 1), 2: ("eighth", 0), 1: ("16th", 0)}
KIND = {"maj": "major", "min": "minor", "7": "dominant", "maj7": "major-seventh", "min7": "minor-seventh", "dim": "diminished",
        "aug": "augmented", "sus4": "suspended-fourth", "sus2": "suspended-second", "maj6": "major-sixth", "min6": "minor-sixth",
        "dim7": "diminished-seventh", "hdim7": "half-diminished", "minmaj7": "major-minor"}


def _pitch(parent: ET.Element, midi: int) -> None:
    name = NAMES[midi % 12]
    p = ET.SubElement(parent, "pitch")
    ET.SubElement(p, "step").text = name[0]
    if len(name) > 1:
        ET.SubElement(p, "alter").text = "1"
    ET.SubElement(p, "octave").text = str(midi // 12 - 1)


def _rest_or_note(m: ET.Element, it: dict, staff: int, tab: bool, stops: dict) -> None:
    n = ET.SubElement(m, "note")
    e = it["event"]
    if e is None:
        ET.SubElement(n, "rest")
    else:
        _pitch(n, int(e["pitch"]))
    ET.SubElement(n, "duration").text = str(it["dur16"])
    ET.SubElement(n, "voice").text = str(staff)
    typ, dots = TYPE[it["dur16"]]
    ET.SubElement(n, "type").text = typ
    for _ in range(dots):
        ET.SubElement(n, "dot")
    ET.SubElement(n, "staff").text = str(staff)
    if e is None:
        return
    nt = ET.SubElement(n, "notations")
    tech = ET.SubElement(nt, "technical")
    if tab:
        ET.SubElement(tech, "string").text = str(e["string"])
        ET.SubElement(tech, "fret").text = str(e["fret"])
    t = e["tech"]
    st = stops.get(id(e))
    if st:
        ET.SubElement(nt if st[0] == "slide" else tech, st[0], {"type": "stop", "number": "1"})
    nxt = t.get("to_next")
    if nxt == "hammer":
        ET.SubElement(tech, "hammer-on", {"type": "start", "number": "1"}).text = "H"
    elif nxt == "pull":
        ET.SubElement(tech, "pull-off", {"type": "start", "number": "1"}).text = "P"
    elif nxt == "slide":
        ET.SubElement(nt, "slide", {"type": "start", "number": "1"})
    on = t.get("on") or []
    if "bend" in on:
        b = ET.SubElement(tech, "bend")
        ET.SubElement(b, "bend-alter").text = str(t.get("bend_semitones", 1))
    if "vibrato" in on:
        ET.SubElement(tech, "other-technical").text = "vibrato"
    if t.get("in") == "slide_in":
        ET.SubElement(nt, "slide", {"type": "start", "number": "2"})
    if not len(tech):
        nt.remove(tech)
    if not len(nt):
        n.remove(nt)


def write_musicxml(model: dict, path: Path) -> dict:
    root = ET.Element("score-partwise", version="3.1")
    ET.SubElement(ET.SubElement(root, "work"), "work-title").text = model["title"] or "MeloTab"
    ident = ET.SubElement(root, "identification")
    ET.SubElement(ET.SubElement(ident, "encoding"), "software").text = "MeloTab"
    pl = ET.SubElement(root, "part-list")
    sp = ET.SubElement(pl, "score-part", id="P1")
    ET.SubElement(sp, "part-name").text = "Guitar"
    part = ET.SubElement(root, "part", id="P1")

    # slide/hammer/pull: โน้ตถัดไปต้องมีปลาย stop
    flat = [it["event"] for m in model["measures"] for it in m["items"] if it["event"] is not None]
    stops: dict[int, tuple[str, int]] = {}
    for a, b in zip(flat, flat[1:]):
        k = a["tech"].get("to_next")
        if k:
            stops[id(b)] = {"hammer": "hammer-on", "pull": "pull-off", "slide": "slide"}[k], 1
    prev_ts = None
    n_notes = 0
    for m in model["measures"]:
        me = ET.SubElement(part, "measure", number=str(m["index"] + 1))
        ts = m["beats"]
        if m["index"] == 0 or ts != prev_ts:
            at = ET.SubElement(me, "attributes")
            if m["index"] == 0:
                ET.SubElement(at, "divisions").text = str(DIV)
                ET.SubElement(ET.SubElement(at, "key"), "fifths").text = "0"
            tm = ET.SubElement(at, "time")
            ET.SubElement(tm, "beats").text = str(ts)
            ET.SubElement(tm, "beat-type").text = "4"
            if m["index"] == 0:
                ET.SubElement(at, "staves").text = "2"
                for num, (sign, line, oct_) in enumerate((("G", "2", "-1"), ("TAB", "5", None)), 1):
                    cl = ET.SubElement(at, "clef", number=str(num))
                    ET.SubElement(cl, "sign").text = sign
                    ET.SubElement(cl, "line").text = line
                    if oct_:
                        ET.SubElement(cl, "clef-octave-change").text = oct_
                sd = ET.SubElement(at, "staff-details", number="2")
                ET.SubElement(sd, "staff-lines").text = "6"
                for i, midi in enumerate(model["tuning"], 1):
                    tu = ET.SubElement(sd, "staff-tuning", line=str(i))
                    ET.SubElement(tu, "tuning-step").text = NAMES[midi % 12][0]
                    if "#" in NAMES[midi % 12]:
                        ET.SubElement(tu, "tuning-alter").text = "1"
                    ET.SubElement(tu, "tuning-octave").text = str(midi // 12 - 1)
                if model["capo"]:
                    ET.SubElement(sd, "capo").text = str(model["capo"])
            prev_ts = ts
        if m["index"] == 0:
            d = ET.SubElement(me, "direction", placement="above")
            dt = ET.SubElement(d, "direction-type")
            met = ET.SubElement(dt, "metronome")
            ET.SubElement(met, "beat-unit").text = "quarter"
            ET.SubElement(met, "per-minute").text = f"{model['bpm']:.0f}"
            ET.SubElement(d, "sound", tempo=f"{model['bpm']:.1f}")
        # คอร์ดที่เริ่มในห้องนี้ (วางที่ต้นห้องหรือ beat ที่คอร์ดเปลี่ยน — ใส่ที่ต้นห้องของ staff 1 ผ่าน harmony ก่อนโน้ตตัวแรก)
        for c in model["chords"]:
            if m["start_beat"] <= c["start_beat"] < m["start_beat"] + m["beats"] and c.get("symbol") not in (None, "N"):
                h = ET.SubElement(me, "harmony")
                if c.get("root") is not None:
                    r = ET.SubElement(h, "root")
                    nm = NAMES[c["root"]]
                    ET.SubElement(r, "root-step").text = nm[0]
                    if len(nm) > 1:
                        ET.SubElement(r, "root-alter").text = "1"
                    ET.SubElement(h, "kind", text=c["symbol"][len(nm):] if c["symbol"].startswith(nm) else "").text = KIND.get(c.get("quality"), "other")
                else:
                    ET.SubElement(h, "kind", text=c["symbol"]).text = "other"
        for staff in (1, 2):
            for it in m["items"]:
                _rest_or_note(me, it, staff, staff == 2, stops)
                n_notes += 1 if (staff == 1 and it["event"] is not None) else 0
            if staff == 1:
                bk = ET.SubElement(me, "backup")
                ET.SubElement(bk, "duration").text = str(m["beats"] * 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space=" ")
    with open(path, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">\n')
        tree.write(f, encoding="utf-8")
    return {"measures": len(model["measures"]), "notes": n_notes}
