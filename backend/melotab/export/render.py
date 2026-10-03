"""Export รูปแทปรายท่อน: วาดเป็นรายการคำสั่ง (เส้น/ข้อความ/สี่เหลี่ยม) แล้วแปลงเป็น SVG, PNG (PIL), PDF (PIL)

หน้าหนึ่ง = หัวกระดาษ (ชื่อเพลง/ท่อน/คีย์/capo/จูนนิ่ง/BPM/ห้อง) + บรรทัดละ [คอร์ด / แทป 6 สาย / เนื้อร้อง] + legend ท้ายหน้า
ถ้าเนื้อหาเกินความสูงของ preset จะแตกเป็นหลายหน้า (ชื่อไฟล์ลงท้าย _p2, _p3 …)
ข้อจำกัด: ไม่มีโน้ตสากลและเลขนิ้วในรูป (ยังไม่ได้ทำ); ฟอนต์ใช้ Leelawadee UI/Tahoma ของ Windows (ถ้าไม่มีจะ fallback เป็นฟอนต์ PIL เริ่มต้น ซึ่งไม่รองรับไทย)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .model import section_bar_range, tech_marks, time_to_beat

PRESETS = {
    "youtube": (1920, 1080), "ig_portrait": (1080, 1350), "story": (1080, 1920), "a4": (1240, 1754),
}
THEMES = {
    "light": {"bg": "#ffffff", "ink": "#16181d", "dim": "#6b7280", "accent": "#1d4ed8", "line": "#9aa1ad", "bar": "#16181d", "warn": "#b45309"},
    "dark": {"bg": "#14161b", "ink": "#eceef2", "dim": "#8b93a1", "accent": "#7aa2ff", "line": "#4a5160", "bar": "#c9ced8", "warn": "#f0b35a"},
    "transparent": {"bg": None, "ink": "#16181d", "dim": "#6b7280", "accent": "#1d4ed8", "line": "#9aa1ad", "bar": "#16181d", "warn": "#b45309"},
}
FONT_DIRS = [r"C:\Windows\Fonts", "/usr/share/fonts/truetype", "/Library/Fonts"]
FONT_REG = ["LeelawUI.ttf", "tahoma.ttf", "segoeui.ttf", "DejaVuSans.ttf"]
FONT_BOLD = ["leelawdb.ttf", "tahomabd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"]
SVG_FONT = "'Leelawadee UI','Tahoma','Segoe UI','Noto Sans Thai',sans-serif"

_font_cache: dict[tuple[bool, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def font(size: int, bold: bool = False):
    key = (bold, size)
    if key not in _font_cache:
        f = None
        for name in (FONT_BOLD if bold else FONT_REG):
            for d in FONT_DIRS:
                p = os.path.join(d, name)
                if os.path.exists(p):
                    f = ImageFont.truetype(p, size)
                    break
            if f:
                break
        _font_cache[key] = f or ImageFont.load_default()
    return _font_cache[key]


def text_w(s: str, size: int, bold: bool = False) -> float:
    f = font(size, bold)
    return float(f.getlength(s)) if hasattr(f, "getlength") else len(s) * size * 0.6


@dataclass
class Canvas:
    w: int
    h: int
    theme: dict
    ops: list[tuple] = field(default_factory=list)

    def line(self, x1, y1, x2, y2, color, width=1.0):
        self.ops.append(("line", x1, y1, x2, y2, color, width))

    def rect(self, x, y, w, h, fill):
        self.ops.append(("rect", x, y, w, h, fill))

    def text(self, x, y, s, size, color, bold=False, anchor="start"):
        if s:
            self.ops.append(("text", x, y, s, size, color, bold, anchor))

    # ---- SVG
    def to_svg(self) -> str:
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" font-family="{SVG_FONT}">']
        if self.theme["bg"]:
            o.append(f'<rect width="100%" height="100%" fill="{self.theme["bg"]}"/>')
        for op in self.ops:
            if op[0] == "line":
                _, x1, y1, x2, y2, c, w = op
                o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="{w}"/>')
            elif op[0] == "rect":
                _, x, y, w, h, c = op
                o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{c}"/>')
            else:
                _, x, y, s, size, c, bold, anchor = op
                fw = ' font-weight="700"' if bold else ""
                o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{c}" text-anchor="{anchor}"{fw}>{escape(s)}</text>')
        o.append("</svg>")
        return "\n".join(o)

    # ---- PNG
    def to_image(self, scale: int = 1) -> Image.Image:
        bg = self.theme["bg"]
        img = Image.new("RGBA", (self.w * scale, self.h * scale), bg if bg else (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for op in self.ops:
            if op[0] == "line":
                _, x1, y1, x2, y2, c, w = op
                d.line([x1 * scale, y1 * scale, x2 * scale, y2 * scale], fill=c, width=max(1, round(w * scale)))
            elif op[0] == "rect":
                _, x, y, w, h, c = op
                d.rectangle([x * scale, y * scale, (x + w) * scale, (y + h) * scale], fill=c)
            else:
                _, x, y, s, size, c, bold, anchor = op
                d.text((x * scale, y * scale), s, fill=c, font=font(max(1, round(size * scale)), bold),
                       anchor={"start": "ls", "middle": "ms", "end": "rs"}[anchor])
        return img


# ---------------------------------------------------------------- layout

PAD = 14            # ช่องว่างซ้าย/ขวาในห้อง
LABEL_W = 36        # ที่ว่างหน้าบรรทัดสำหรับ "TAB"
LINE_GAP = 17
ROW_CHORD, ROW_LYRIC = 30, 28


def _bar_layout(m: dict, px_beat: float) -> tuple[float, list[tuple[float, dict]]]:
    """(ความกว้างขั้นต่ำของห้อง, [(x สัมพัทธ์ภายในห้อง, item)]) — กันเลขช่องทับกันโดยดันไปทางขวา/ขยายห้อง"""
    ideal = max(m["beats"] * px_beat, 2 * PAD + 30)
    inner = ideal - 2 * PAD
    pos = []
    prev_right = -1e9
    for it in m["items"]:
        e = it["event"]
        if not e:
            continue
        label = str(e["fret"]) + tech_marks(e["tech"])
        wl = text_w(label, 15, True) + 5
        x = PAD + it["start16"] / (m["beats"] * 4) * inner
        x = max(x, prev_right + wl / 2 + 1)
        prev_right = x + wl / 2
        pos.append((x, it))
    need = (pos[-1][0] + PAD) if pos else ideal
    return max(ideal, need + 6), pos


def _pack(measures: list[dict], px_beat: float, avail: float) -> list[list[tuple[dict, float, list]]]:
    systems: list[list[tuple[dict, float, list]]] = []
    cur: list[tuple[dict, float, list]] = []
    used = 0.0
    for m in measures:
        w, pos = _bar_layout(m, px_beat)
        if cur and used + w > avail:
            systems.append(cur)
            cur, used = [], 0.0
        cur.append((m, w, pos))
        used += w
    if cur:
        systems.append(cur)
    return systems


def render_pages(model: dict, section: dict | None, *, preset: str = "youtube", theme: str = "light", size: tuple[int, int] | None = None,
                 show_chords: bool = True, show_lyrics: bool = True, watermark: str = "") -> list[Canvas]:
    W, H = size or PRESETS.get(preset, PRESETS["youtube"])
    th = THEMES.get(theme, THEMES["light"])
    margin = round(W * 0.035)
    avail = W - 2 * margin - LABEL_W
    px_beat = max(44.0, min(78.0, W / 30))
    if section:
        a, b = section_bar_range(model, section)
    else:
        a, b = 0, len(model["measures"])
    measures = model["measures"][a:b]
    systems = _pack(measures, px_beat, avail)
    lyrics_lines = ((model.get("lyrics") or {}).get("lines") or []) if show_lyrics else []
    beats = model["beats"]

    title = model["title"] or "MeloTab"
    sec_name = (section or {}).get("label", "")
    cap = f"Capo {model['capo']}" if model["capo"] else "No capo"
    ts = model["time_signature"]
    info = f"Key {model['key'] or '-'}  ·  {cap}  ·  Tuning {model['tuning_name']}  ·  BPM {model['bpm']:.0f}  ·  {ts['num']}/{ts['den']}"
    head_h = 112 if sec_name else 84
    sys_h = (ROW_CHORD if show_chords else 8) + 5 * LINE_GAP + 26 + (ROW_LYRIC if lyrics_lines else 0) + 22
    foot_h = 46

    pages: list[Canvas] = []
    cv: Canvas | None = None
    y = 0.0

    def new_page() -> None:
        nonlocal cv, y
        cv = Canvas(W, H, th)
        pages.append(cv)
        cv.text(margin, margin + 34, title, 34, th["ink"], bold=True)
        if sec_name:
            cv.text(margin, margin + 70, f"{sec_name}", 26, th["accent"], bold=True)
        cv.text(margin, margin + head_h - 14, info, 17, th["dim"])
        y = margin + head_h + 12
        legend = "h = hammer-on   p = pull-off   / = slide   b = bend   ~ = vibrato"
        cv.text(margin, H - margin + 4, legend, 15, th["dim"])
        if watermark:
            cv.text(W - margin, H - margin + 4, watermark, 15, th["dim"], anchor="end")

    new_page()
    for si, sysm in enumerate(systems):
        if y + sys_h > H - margin - foot_h:
            new_page()
        assert cv is not None
        natural = sum(w for _, w, _ in sysm)
        k = avail / natural if (si < len(systems) - 1 or natural > avail * 0.7) else 1.0
        k = min(k, 1.5) if si == len(systems) - 1 else k
        top = y + (ROW_CHORD if show_chords else 8)
        bottom = top + 5 * LINE_GAP
        x0 = margin + LABEL_W
        # เส้นสาย + ป้าย TAB
        total_w = natural * k
        for s in range(6):
            cv.line(x0, top + s * LINE_GAP, x0 + total_w, top + s * LINE_GAP, th["line"], 1.2)
        for i, ch in enumerate("TAB"):
            cv.text(margin + LABEL_W / 2 - 2, top + 1.35 * LINE_GAP + i * 0.95 * LINE_GAP * 0.78 + 4, ch, 15, th["ink"], bold=True, anchor="middle")
        x = x0
        for m, w, pos in sysm:
            ww = w * k
            cv.line(x, top, x, bottom, th["bar"], 1.6)
            cv.text(x + 4, bottom + 16, str(m["index"] + 1), 12, th["dim"])
            for px, it in pos:
                e = it["event"]
                fx = x + px * k
                fy = top + (e["string"] - 1) * LINE_GAP
                label = str(e["fret"]) + tech_marks(e["tech"])
                lw = text_w(label, 15, True)
                cv.rect(fx - lw / 2 - 1.5, fy - 8.5, lw + 3, 17, th["bg"] or "#ffffff")
                cv.text(fx, fy + 5.5, label, 15, th["ink"], bold=True, anchor="middle")
            if show_chords:
                last = None
                for c in model["chords"]:
                    if m["start_beat"] <= c["start_beat"] < m["start_beat"] + m["beats"] and c.get("symbol") not in (None, "N"):
                        if c["symbol"] == last:
                            continue
                        last = c["symbol"]
                        cx = x + PAD * k + (c["start_beat"] - m["start_beat"]) / m["beats"] * (ww - 2 * PAD * k)
                        cv.text(cx, top - 8, c["symbol"], 20, th["accent"], bold=True)
            x += ww
        cv.line(x, top, x, bottom, th["bar"], 1.6)
        if lyrics_lines:
            ly = bottom + 40
            for ln in lyrics_lines:
                for wd in ln.get("words", []):
                    bt = time_to_beat(beats, wd["start"])
                    xx = x0
                    for m, w, pos in sysm:
                        if m["start_beat"] <= bt < m["start_beat"] + m["beats"]:
                            cx = xx + PAD * k + (bt - m["start_beat"]) / m["beats"] * (w * k - 2 * PAD * k)
                            cv.text(cx, ly, wd["text"], 17, th["ink"])
                            break
                        xx += w * k
        y += sys_h
    return pages
