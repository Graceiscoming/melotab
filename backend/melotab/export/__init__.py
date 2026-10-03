"""Export (Phase 5): รูปแทปรายท่อน PNG/SVG/PDF, MIDI, MusicXML, Guitar Pro 5, text tab, chord sheet, LRC, stems

อ่านจากไฟล์ที่บันทึกไว้ในโปรเจกต์ (song.json + tab.json) แล้วเขียนผลลงโฟลเดอร์ `exports/` ของโปรเจกต์
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import gp, midi, musicxml, render, text
from .model import build, section_bar_range

FORMATS = ("png", "svg", "pdf", "midi", "musicxml", "gp5", "txt", "chordsheet", "lrc", "stems", "video", "harmony")
IMAGE_FORMATS = ("png", "svg", "pdf")


def safe_name(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", s).strip(" .")
    return s[:80] or "melotab"


def run_export(project_dir: Path, song: dict, tab: dict | None, stem_path, req: dict) -> dict:
    """req: formats, sections ('all' | [id,...] | []=ทั้งเพลง), custom_range {start,end}, preset, theme, scale, show_chords, show_lyrics,
    watermark, midi_quantized. คืน {"dir", "files": [{name, size, format}], "skipped": [{format, reason}]}"""
    formats = [f for f in req.get("formats", []) if f in FORMATS]
    unknown = [f for f in req.get("formats", []) if f not in FORMATS]
    if unknown:
        raise ValueError(f"ไม่รู้จักฟอร์แมต: {', '.join(unknown)}")
    if not formats:
        raise ValueError("ยังไม่ได้เลือกฟอร์แมต")
    out_dir = project_dir / "exports"
    out_dir.mkdir(exist_ok=True)
    title = song.get("source", {}).get("title", "") or project_dir.name
    base = safe_name(title)
    model = build(song, tab, title)
    files: list[dict] = []
    skipped: list[dict] = []

    def add(p: Path, fmt: str) -> None:
        files.append({"name": p.name, "size": p.stat().st_size, "format": fmt})

    secs_all = song.get("sections") or []
    want = req.get("sections", [])
    if want == "all":
        chosen = list(secs_all)
    else:
        chosen = [s for s in secs_all if s.get("id") in set(want)]
    if req.get("custom_range"):
        r = req["custom_range"]
        chosen.append({"id": "custom", "label": "ช่วงที่เลือก", "start": float(r["start"]), "end": float(r["end"])})
    has_tab = bool(tab and tab.get("events"))

    def numbered(sec: dict | None) -> str:
        if sec is None:
            return base
        idx = next((i for i, s in enumerate(secs_all, 1) if s.get("id") == sec.get("id")), 0)
        return f"{base}_{idx:02d}_{safe_name(sec.get('label', 'section'))}" if idx else f"{base}_{safe_name(sec.get('label', 'ช่วง'))}"

    img_fmts = [f for f in formats if f in IMAGE_FORMATS]
    if img_fmts:
        if not has_tab:
            for f in img_fmts:
                skipped.append({"format": f, "reason": "ยังไม่มีแทป (สร้างแทปก่อน)"})
        else:
            targets = chosen or [None]
            scale = max(1, min(4, int(req.get("scale", 1))))
            opts = dict(preset=req.get("preset", "youtube"), theme=req.get("theme", "light"),
                        show_chords=bool(req.get("show_chords", True)), show_lyrics=bool(req.get("show_lyrics", True)),
                        watermark=req.get("watermark", ""))
            book = []
            for sec in targets:
                pages = render.render_pages(model, sec, **opts)
                for pi, cv in enumerate(pages, 1):
                    stem = numbered(sec) + (f"_p{pi}" if len(pages) > 1 else "")
                    if "svg" in img_fmts:
                        p = out_dir / f"{stem}.svg"
                        p.write_text(cv.to_svg(), encoding="utf-8")
                        add(p, "svg")
                    if "png" in img_fmts or "pdf" in img_fmts:
                        img = cv.to_image(scale)
                        if "png" in img_fmts:
                            p = out_dir / f"{stem}.png"
                            img.save(p)
                            add(p, "png")
                        if "pdf" in img_fmts:
                            from PIL import Image
                            flat = Image.new("RGB", img.size, "white")
                            flat.paste(img, mask=img.split()[3])
                            book.append(flat)
            if "pdf" in img_fmts and book:
                p = out_dir / f"{base}{'_tab' if len(targets) == 1 and targets[0] else ''}.pdf"
                book[0].save(p, "PDF", save_all=True, append_images=book[1:], resolution=150.0 * scale)
                add(p, "pdf")

    if "midi" in formats:
        p = out_dir / f"{base}.mid"
        midi.write_midi(song, p, quantized=bool(req.get("midi_quantized", False)))
        add(p, "midi")
    for fmt, ext, fn in (("musicxml", ".musicxml", musicxml.write_musicxml), ("gp5", ".gp5", gp.write_gp5)):
        if fmt in formats:
            if not has_tab:
                skipped.append({"format": fmt, "reason": "ยังไม่มีแทป (สร้างแทปก่อน)"})
                continue
            p = out_dir / f"{base}{ext}"
            fn(model, p)
            add(p, fmt)
    if "txt" in formats:
        if not has_tab:
            skipped.append({"format": "txt", "reason": "ยังไม่มีแทป (สร้างแทปก่อน)"})
        else:
            p = out_dir / f"{base}_tab.txt"
            p.write_text(text.tab_document(model, chosen or None), encoding="utf-8")
            add(p, "txt")
    if "chordsheet" in formats:
        if not song.get("chords"):
            skipped.append({"format": "chordsheet", "reason": "ยังไม่มีคอร์ด"})
        else:
            p = out_dir / f"{base}_chords.txt"
            p.write_text(text.chord_sheet_text(model, chosen or None), encoding="utf-8")
            add(p, "chordsheet")
    if "lrc" in formats:
        if not (song.get("lyrics") or {}).get("lines"):
            skipped.append({"format": "lrc", "reason": "ยังไม่มีเนื้อร้อง"})
        else:
            p = out_dir / f"{base}.lrc"
            p.write_text(text.lrc_text(song), encoding="utf-8")
            add(p, "lrc")
    if "video" in formats:
        if not has_tab:
            skipped.append({"format": "video", "reason": "ยังไม่มีแทป (สร้างแทปก่อน)"})
        else:
            from . import video
            for sec in (chosen or [None]):
                p = out_dir / f"{numbered(sec)}.mp4"
                video.render_video(model, sec, p, stem_path("mix"), fps=int(req.get("video_fps", 15)))
                add(p, "video")
    if "harmony" in formats:
        from ..harmony import generate as gen_harmony
        from ..tab import generate_tab
        hs = req.get("harmony") or {}
        try:
            hn = gen_harmony(song.get("notes", []), song.get("key"), song.get("chords"), interval=hs.get("interval", "third"),
                             direction=hs.get("direction", "above"))
        except ValueError as e:
            skipped.append({"format": "harmony", "reason": str(e)})
        else:
            hsong = {**song, "notes": hn, "chords": song.get("chords")}
            p = out_dir / f"{base}_harmony.mid"
            midi.write_midi(hsong, p, with_chords=False)
            add(p, "harmony")
            htab = generate_tab(hn, (tab or {}).get("settings") or {})
            p = out_dir / f"{base}_harmony_tab.txt"
            p.write_text(text.tab_document(build(hsong, htab, title + " (harmony)"), chosen or None), encoding="utf-8")
            add(p, "harmony")
    if "stems" in formats:
        found = 0
        for st in ("vocals", "instrumental", "lead", "backing"):
            src = stem_path(st)
            if src:
                p = out_dir / f"{base}_{st}{src.suffix}"
                shutil.copyfile(src, p)
                add(p, "stems")
                found += 1
        if not found:
            skipped.append({"format": "stems", "reason": "ไม่พบไฟล์ stem"})
    return {"dir": str(out_dir), "files": files, "skipped": skipped}


__all__ = ["FORMATS", "run_export", "build", "section_bar_range"]
