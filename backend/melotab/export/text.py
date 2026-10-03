"""Export ข้อความ: Text tab (.txt), Chord sheet (.txt), LRC (.lrc)"""
from __future__ import annotations

import unicodedata

from .model import chord_at_beat, section_bar_range, tech_marks, time_to_beat

SLOT = 3                                                     # ตัวอักษรต่อ 1/16 ใน text tab (เลขช่อง ≤ 2 หลัก + สัญลักษณ์เทคนิค 1 ตัว)
STRING_NAMES = {1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E"}


def width(s: str) -> int:
    """ความกว้างตอนแสดงในฟอนต์ monospace: ตัวสระ/วรรณยุกต์ไทย (combining) กว้าง 0"""
    return sum(0 if unicodedata.combining(c) or unicodedata.category(c) in ("Mn", "Me", "Cf") else 1 for c in s)


def _bar_cells(m: dict) -> list[list[str]]:
    """6 สาย × (beats*4*SLOT) ตัวอักษรของห้องหนึ่ง"""
    n = m["beats"] * 4 * SLOT
    rows = [["-"] * n for _ in range(6)]
    for it in m["items"]:
        e = it["event"]
        if not e:
            continue
        txt = str(e["fret"]) + tech_marks(e["tech"])
        row = rows[e["string"] - 1]
        x = it["start16"] * SLOT
        for i, ch in enumerate(txt[:SLOT]):
            row[x + i] = ch
    return rows


def tab_text(model: dict, bars: tuple[int, int] | None = None, per_row: int | None = None, max_width: int = 100) -> str:
    ms = model["measures"][bars[0]:bars[1]] if bars else model["measures"]
    out: list[str] = []
    row: list[dict] = []
    row_w = 0

    def flush() -> None:
        nonlocal row, row_w
        if not row:
            return
        cells = [_bar_cells(m) for m in row]
        head = " " * 2 + "".join(f"{m['index'] + 1:<{len(c[0]) + 1}}" for m, c in zip(row, cells))
        out.append(head.rstrip())
        for s in range(6):
            out.append(f"{STRING_NAMES[s + 1]}|" + "|".join("".join(c[s]) for c in cells) + "|")
        out.append("")
        row, row_w = [], 0

    for m in ms:
        w = m["beats"] * 4 * SLOT + 1
        if row and ((per_row and len(row) >= per_row) or (not per_row and row_w + w > max_width)):
            flush()
        row.append(m)
        row_w += w
    flush()
    return "\n".join(out).rstrip() + "\n"


def header_text(model: dict) -> str:
    cap = f"Capo {model['capo']}" if model["capo"] else "No capo"
    ts = model["time_signature"]
    return (f"{model['title']}\nKey: {model['key'] or '-'} · {cap} · Tuning: {model['tuning_name']}"
            f" · BPM {model['bpm']:.0f} · {ts['num']}/{ts['den']}\n"
            f"สัญลักษณ์: h=hammer-on p=pull-off /=slide b=bend ~=vibrato\n\n")


def tab_document(model: dict, sections: list[dict] | None = None) -> str:
    txt = header_text(model)
    if sections:
        for s in sections:
            a, b = section_bar_range(model, s)
            txt += f"[{s.get('label', 'Section')}]\n" + tab_text(model, (a, b)) + "\n"
    else:
        txt += tab_text(model)
    return txt


# ---------------------------------------------------------------- chord sheet

def _lyric_line_with_chords(model: dict, line: dict) -> list[str]:
    """บรรทัดเนื้อ + แถวคอร์ดเหนือคำที่คอร์ดเริ่ม (จัดตำแหน่งตามความกว้างตัวอักษรจริง)"""
    beats = model["beats"]
    words = line.get("words") or []
    if not words:
        return [line["text"]]
    text = ""
    marks: list[tuple[int, str]] = []
    last_sym = None
    for w in words:
        c = chord_at_beat(model["chords"], time_to_beat(beats, w["start"]))
        sym = c["symbol"] if c and c.get("symbol") not in (None, "N") else None
        if sym and sym != last_sym:
            marks.append((width(text), sym))
            last_sym = sym
        text += w["text"] + (" " if w["text"] and w["text"][-1].isascii() and w["text"][-1].isalnum() else "")
    chord_row = ""
    for pos, sym in marks:
        chord_row += " " * max(0, pos - width(chord_row)) + sym + " "
    return [chord_row.rstrip(), text.rstrip()] if chord_row.strip() else [text.rstrip()]


def chord_sheet_text(model: dict, sections: list[dict] | None = None) -> str:
    out = [header_text(model).rstrip(), ""]
    secs = sections or model["sections"] or [{"label": "", "start": 0.0, "end": 1e9}]
    lines = (model.get("lyrics") or {}).get("lines") or []
    for s in secs:
        out.append(f"[{s.get('label') or 'Song'}]")
        a, b = section_bar_range(model, s) if model["measures"] else (0, 0)
        t0 = s.get("start", 0.0)
        t1 = s.get("end", 1e9)
        sec_lines = [ln for ln in lines if t0 - 0.01 <= ln["start"] < t1]
        if sec_lines:
            for ln in sec_lines:
                out += _lyric_line_with_chords(model, ln)
                out.append("")
        else:                                              # ไม่มีเนื้อ → แสดงลำดับคอร์ดต่อห้อง
            cells = []
            for m in model["measures"][a:b]:
                syms = []
                for c in model["chords"]:
                    if m["start_beat"] <= c["start_beat"] < m["start_beat"] + m["beats"] and c.get("symbol") not in (None, "N"):
                        syms.append(c["symbol"])
                if not syms:
                    c0 = chord_at_beat(model["chords"], m["start_beat"])
                    syms = [c0["symbol"]] if c0 and c0.get("symbol") not in (None, "N") else ["%"]
                cells.append(" ".join(syms))
            for i in range(0, len(cells), 4):
                out.append("| " + " | ".join(cells[i:i + 4]) + " |")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def lrc_text(song: dict) -> str:
    lines = (song.get("lyrics") or {}).get("lines") or []
    title = song.get("source", {}).get("title", "")
    out = [f"[ti:{title}]"]
    for ln in lines:
        t = max(0.0, ln["start"])
        out.append(f"[{int(t // 60):02d}:{t % 60:05.2f}]{ln['text']}")
    return "\n".join(out) + "\n"
