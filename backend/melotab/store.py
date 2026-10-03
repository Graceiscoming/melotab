"""ที่เก็บโปรเจกต์แบบโฟลเดอร์ (plan หัวข้อ 16.1) — เวอร์ชันพื้นฐานของ Phase 1

Projects/<id>/ : project.json, source/<ไฟล์เดิม>, audio/, analysis/, song.json, melody.mid
ยังไม่มี SQLite index / autosave / history (ขั้น "Project save/load" ถัดไป)
"""
import json
import re
import shutil
import time
import uuid
from pathlib import Path

from .config import ROOT

DEFAULT_PROJECTS_DIR = ROOT / "Projects"
ID_RE = re.compile(r"^[0-9A-Za-z_\-฀-๿]{1,80}$")      # อนุญาตไทย/ตัวเลข/ขีด กัน path traversal
STEMS = {"mix", "vocals", "instrumental", "lead", "backing", "lead_dry"}


def _slug(text: str) -> str:
    s = re.sub(r"[^0-9A-Za-z฀-๿]+", "-", text).strip("-")
    return s[:40] or "song"


class ProjectStore:
    def __init__(self, root: Path = DEFAULT_PROJECTS_DIR):
        self.root = Path(root)

    def path(self, project_id: str) -> Path:
        if not ID_RE.match(project_id):
            raise ValueError("project id ไม่ถูกต้อง")
        return self.root / project_id

    def create(self, source: Path, title: str | None = None) -> dict:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(f"ไม่พบไฟล์: {source}")
        title = title or source.stem
        pid = f"{time.strftime('%Y-%m-%d')}_{_slug(title)}_{uuid.uuid4().hex[:4]}"
        d = self.path(pid)
        (d / "source").mkdir(parents=True)
        shutil.copy2(source, d / "source" / source.name)
        meta = {"id": pid, "title": title, "source_file": source.name, "created": time.time(), "version": 1}
        (d / "project.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        return meta

    def source_path(self, project_id: str) -> Path:
        meta = self.meta(project_id)
        return self.path(project_id) / "source" / meta["source_file"]

    def meta(self, project_id: str) -> dict:
        f = self.path(project_id) / "project.json"
        if not f.exists():
            raise FileNotFoundError(project_id)
        return json.loads(f.read_text(encoding="utf-8"))

    def list(self) -> list[dict]:
        if not self.root.exists():
            return []
        out = []
        for p in sorted(self.root.glob("*/project.json"), reverse=True):
            m = json.loads(p.read_text(encoding="utf-8"))
            m["analyzed"] = (p.parent / "song.json").exists()
            out.append(m)
        return out

    def song(self, project_id: str) -> dict | None:
        f = self.path(project_id) / "song.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

    def stem_path(self, project_id: str, stem: str) -> Path | None:
        if stem not in STEMS:
            return None
        base = self.path(project_id) / "audio"
        p = base / "mix.mp3" if stem == "mix" else base / "stems" / f"{stem}.flac"
        return p if p.exists() else None

    def f0_curve(self, project_id: str, step: int = 2) -> dict | None:
        """เส้น pitch สำหรับวาดบน piano roll: เวลา (s) + MIDI (ทศนิยม, null = unvoiced) ลดความถี่ลงทุก `step` เฟรม (20 ms)"""
        import numpy as np
        f = self.path(project_id) / "analysis" / "f0.npz"
        if not f.exists():
            return None
        z = np.load(f)
        hz, t = z["f0_hz"][::step], z["times"][::step]
        midi = np.where(hz > 0, 69 + 12 * np.log2(np.maximum(hz, 1e-3) / 440.0), np.nan)
        return {"hop_s": float(z["hop_s"]) * step, "t0": float(t[0]) if len(t) else 0.0,
                "midi": [None if np.isnan(m) else round(float(m), 2) for m in midi]}

    def save_song(self, project_id: str, song: dict) -> None:
        """บันทึกโน้ตที่แก้ไขแล้ว (เขียนไฟล์ชั่วคราวแล้วค่อยแทน กันไฟล์พังตอนปิดโปรแกรมกลางคัน)"""
        d = self.path(project_id)
        if not (d / "project.json").exists():
            raise FileNotFoundError(project_id)
        tmp = d / "song.json.tmp"
        tmp.write_text(json.dumps(song, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(d / "song.json")
