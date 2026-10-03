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
STEMS = {"vocals", "instrumental", "lead", "backing", "lead_dry", "source"}


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
        p = base / "source.wav" if stem == "source" else base / "stems" / f"{stem}.flac"
        return p if p.exists() else None
